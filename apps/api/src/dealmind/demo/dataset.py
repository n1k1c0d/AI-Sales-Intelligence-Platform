"""In-memory mapped records, with no engine, session or implicit database defaults."""

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import inspect

from dealmind.db.base import Base
from dealmind.models import (
    Activity,
    Contact,
    Deal,
    DealStageHistory,
    Organization,
    Pipeline,
    PipelineStage,
    User,
)

from .config import VERSION, Config

NAMESPACE = uuid5(NAMESPACE_URL, "urn:dealmind:demo:dealmind-demo")


def uid(key: str) -> UUID:
    return uuid5(NAMESPACE, key)


def utc(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def configuration(config: Config) -> dict[str, object]:
    result = config.model_dump(mode="json")
    result["anchor_datetime"] = utc(config.anchor_datetime)
    for key in ("open_ratio", "won_ratio", "lost_ratio"):
        result[key] = format(Decimal(result[key]).normalize(), "f")
    return {"generator_version": VERSION, **result}


def json_scalar(value: object) -> str:
    if isinstance(value, datetime):
        return utc(value)
    if isinstance(value, Decimal):
        return format(value, ".2f")
    if isinstance(value, UUID):
        return str(value)
    raise TypeError(f"Unexpected dataset value: {type(value).__name__}")


def canonical(value: object) -> bytes:
    return json.dumps(
        value,
        default=json_scalar,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def records(model: type[Base], rows: Sequence[Base]) -> list[dict[str, object]]:
    mapper = inspect(model)
    assert mapper is not None
    fields = [(p.columns[0].name, p.key) for p in mapper.column_attrs]
    return [{col: getattr(row, attr) for col, attr in fields} for row in rows]


@dataclass
class Dataset:
    config: Config
    organizations: list[Organization] = field(default_factory=list)
    users: list[User] = field(default_factory=list)
    contacts: list[Contact] = field(default_factory=list)
    pipelines: list[Pipeline] = field(default_factory=list)
    stages: list[PipelineStage] = field(default_factory=list)
    deals: list[Deal] = field(default_factory=list)
    activities: list[Activity] = field(default_factory=list)
    history: list[DealStageHistory] = field(default_factory=list)
    references: dict[str, UUID] = field(default_factory=dict)
    fingerprint: str = ""

    def groups(self) -> tuple[tuple[type[Base], Sequence[Base]], ...]:
        return (
            (Organization, self.organizations),
            (User, self.users),
            (Contact, self.contacts),
            (Pipeline, self.pipelines),
            (PipelineStage, self.stages),
            (Deal, self.deals),
            (Activity, self.activities),
            (DealStageHistory, self.history),
        )

    def counts(self) -> dict[str, int]:
        return {m.__tablename__: len(rows) for m, rows in self.groups()}

    def digest(self) -> str:
        tables = {
            m.__tablename__: sorted(records(m, rows), key=lambda r: str(r["id"]))
            for m, rows in self.groups()
        }
        return hashlib.sha256(
            canonical([configuration(self.config), tables, self.references])
        ).hexdigest()
