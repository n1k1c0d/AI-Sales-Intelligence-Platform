import re

import psycopg
import pytest
import sqlalchemy as sa
from psycopg import sql

from dealmind import models
from dealmind.core.config import Settings
from dealmind.db.base import Base

from .support import migrate, sql_connection, temporary_database

pytestmark = pytest.mark.database

CRM_TABLES = {
    "organizations",
    "users",
    "contacts",
    "pipelines",
    "pipeline_stages",
    "deals",
    "activities",
    "deal_stage_history",
}


def public_tables(check: psycopg.Connection[tuple[object, ...]]) -> set[str]:
    rows = check.execute("SELECT tablename FROM pg_tables WHERE schemaname='public'").fetchall()
    return {str(row[0]) for row in rows}


def assert_catalog(check: psycopg.Connection[tuple[object, ...]]) -> None:
    assert public_tables(check) == CRM_TABLES | {"alembic_version"}
    assert models.Deal.metadata is Base.metadata
    for table in Base.metadata.sorted_tables:
        names = check.execute(
            "SELECT conname FROM pg_constraint WHERE conrelid = %s::regclass", (table.name,)
        ).fetchall()
        assert {row[0] for row in names} == {constraint.name for constraint in table.constraints}
        for column in table.columns:
            if isinstance(column.type, sa.Enum):
                definition = check.execute(
                    "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                    "WHERE conrelid=%s::regclass AND conname=%s AND contype='c'",
                    (table.name, f"ck_{table.name}_{column.name}"),
                ).fetchone()
                assert definition and isinstance(definition[0], str)
                assert set(re.findall(r"'([^']*)'", definition[0])) == set(column.type.enums)
        keys = check.execute(
            "SELECT indexname FROM pg_indexes WHERE schemaname='public' AND tablename=%s",
            (table.name,),
        ).fetchall()
        expected_indexes = {index.name for index in table.indexes} | {
            c.name
            for c in table.constraints
            if isinstance(c, (sa.PrimaryKeyConstraint, sa.UniqueConstraint))
        }
        assert {row[0] for row in keys} == expected_indexes
        actual_columns = check.execute(
            "SELECT column_name, is_nullable FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name=%s",
            (table.name,),
        ).fetchall()
        assert {row[0]: row[1] for row in actual_columns} == {
            c.name: "YES" if c.nullable else "NO" for c in table.columns
        }
        assert check.execute(
            sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(table.name))
        ).fetchone() == (0,)
    actions = check.execute(
        "SELECT confdeltype, confupdtype, confmatchtype FROM pg_constraint "
        "WHERE contype='f' AND connamespace='public'::regnamespace"
    ).fetchall()
    assert len(actions) == 18 and set(actions) == {("r", "r", "s")}


def test_baseline_round_trip_on_fresh_database(db_settings: Settings) -> None:
    with temporary_database(db_settings) as settings, sql_connection(settings) as check:
        vector = "SELECT extversion FROM pg_extension WHERE extname='vector'"
        revision = "SELECT version_num FROM alembic_version"
        assert not public_tables(check)
        assert check.execute(vector).fetchone() is None
        assert migrate(settings, "heads").strip() == "0002 (head)"
        assert "0001 -> 0002" in migrate(settings, "history")

        migrate(settings, "upgrade", "head")
        migrate(settings, "upgrade", "head")
        assert check.execute(revision).fetchall() == [("0002",)]
        assert "0002 (head)" in migrate(settings, "current")
        assert_catalog(check)
        assert "No new upgrade operations" in migrate(settings, "check")

        migrate(settings, "downgrade", "0001")
        assert public_tables(check) == {"alembic_version"}
        assert check.execute(revision).fetchall() == [("0001",)]
        assert check.execute(vector).fetchone() == ("0.8.7",)

        # Preserve the original DM-007 downgrade and extension regression.
        migrate(settings, "downgrade", "base")
        assert check.execute(revision).fetchall() == []
        assert check.execute(vector).fetchone() == ("0.8.7",)
        row = check.execute("SELECT '[1,0,0]'::vector <-> '[0,1,0]'::vector").fetchone()
        assert row and row[0] == pytest.approx(2**0.5)
        migrate(settings, "upgrade", "0001")
        assert public_tables(check) == {"alembic_version"}
        migrate(settings, "upgrade", "head")
        assert check.execute(revision).fetchall() == [("0002",)]
        assert_catalog(check)
        assert "No new upgrade operations" in migrate(settings, "check")
