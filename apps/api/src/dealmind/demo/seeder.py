"""Transactional, insert-only persistence for the fixed DealMind demo namespace."""

import ipaddress
import re
from dataclasses import dataclass
from typing import Literal

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from dealmind.core.config import Settings
from dealmind.db.engine import create_database_engine
from dealmind.db.session import create_session_factory
from dealmind.models import Organization

from .dataset import Dataset, records, uid
from .validator import validate


class UnsafeTarget(ValueError):
    pass


class Conflict(ValueError):
    pass


class VerificationError(RuntimeError):
    pass


@dataclass(frozen=True)
class SeedResult:
    status: Literal["CREATED", "ALREADY_EXISTS"]
    inserted: dict[str, int]
    verified: dict[str, int]


def check_target(settings: Settings, apply: bool) -> None:
    if not apply or settings.env not in ("local", "test"):
        raise UnsafeTarget("Writing requires --apply and an explicit local or test environment")
    if (
        not {"env", "db_host", "db_port", "db_name", "db_user", "db_password"}
        <= settings.model_fields_set
        or settings.db_password is None
    ):
        raise UnsafeTarget("Set APP_ENV and all five APP_DB connection settings explicitly")
    if settings.db_host not in ("127.0.0.1", "::1"):
        raise UnsafeTarget("Use an explicit loopback address for the local PostgreSQL endpoint")
    if not re.fullmatch(r"dealmind_(demo|test)(_[a-z0-9_]+)?", settings.db_name):
        raise UnsafeTarget("Choose a dedicated dealmind_demo or dealmind_test database")


async def inspect_target(session: AsyncSession, settings: Settings) -> None:
    await session.execute(sa.text("SET LOCAL search_path TO pg_catalog, public"))
    database, user, address = (
        await session.execute(
            sa.text("SELECT current_database(), current_user, inet_server_addr()::text")
        )
    ).one()
    if (
        database != settings.db_name
        or user != settings.db_user
        or not address
        or not ipaddress.ip_address(address.split("/")[0]).is_private
    ):
        raise UnsafeTarget(
            "Connected database, role or server address does not match the local target"
        )
    if not await session.scalar(sa.text("SELECT to_regclass('public.alembic_version')")):
        raise UnsafeTarget("Missing Alembic schema; expected revision 0002")
    versions = (
        await session.scalars(sa.text("SELECT version_num FROM public.alembic_version"))
    ).all()
    if versions != ["0002"]:
        raise UnsafeTarget("Incompatible Alembic revision; expected 0002")


async def compare_rows(session: AsyncSession, data: Dataset) -> dict[str, int]:
    counts = {}
    org = data.organizations[0].id
    for model, rows in data.groups():
        table = model.metadata.tables[model.__tablename__]
        scope = table.c.id if model is Organization else table.c.organization_id
        stored = (await session.execute(sa.select(table).where(scope == org))).mappings().all()
        expected = {row["id"]: row for row in records(model, rows)}
        if len(stored) != len(expected) or any(
            dict(row) != expected.get(row["id"]) for row in stored
        ):
            raise Conflict(f"Stored records differ in {table.name}; no replacement performed")
        counts[table.name] = len(stored)
    return counts


async def seed(data: Dataset, settings: Settings, *, apply: bool = False) -> SeedResult:
    check_target(settings, apply)
    validate(data)
    engine = create_database_engine(settings)
    sessions = create_session_factory(engine)
    inserted = {k: 0 for k in data.counts()}
    try:
        async with sessions.begin() as session:
            await session.execute(sa.text("SET TRANSACTION ISOLATION LEVEL READ COMMITTED"))
            await inspect_target(session, settings)
            lock_key = int.from_bytes(uid("organization").bytes[:8], "big", signed=True)
            await session.execute(sa.text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock_key})
            exists = await session.scalar(
                sa.select(Organization.id).where(Organization.id == data.organizations[0].id)
            )
            if exists is not None:
                await compare_rows(session, data)
            else:
                for model, rows in data.groups():
                    table = model.metadata.tables[model.__tablename__]
                    await session.execute(table.insert(), records(model, rows))
                    inserted[table.name] = len(rows)
        # A fresh session reads all tables from one PostgreSQL snapshot after commit.
        try:
            async with sessions.begin() as reader:
                await reader.execute(
                    sa.text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
                )
                await inspect_target(reader, settings)
                verified = await compare_rows(reader, data)
        except (sa.exc.SQLAlchemyError, Conflict, UnsafeTarget) as exc:
            raise VerificationError(
                "Transaction completed; post-commit verification failed. Data may already be present."
            ) from exc
        return SeedResult("ALREADY_EXISTS" if exists else "CREATED", inserted, verified)
    except sa.exc.IntegrityError as exc:
        if getattr(exc.orig, "sqlstate", None) == "23505":
            raise Conflict(
                "A stored identifier conflicts with the demo dataset; transaction rolled back"
            ) from exc
        raise
    finally:
        await engine.dispose()
