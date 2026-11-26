"""Shared mapped columns and constraints for the eight CRM tables."""

from datetime import datetime
from enum import StrEnum
from typing import Annotated
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.orm import mapped_column

PrimaryId = Annotated[UUID, mapped_column(sa.Uuid, primary_key=True, default=uuid4)]
OrganizationId = Annotated[
    UUID, mapped_column(sa.ForeignKey("organizations.id", onupdate="RESTRICT", ondelete="RESTRICT"))
]
Instant = Annotated[datetime, mapped_column(sa.DateTime(timezone=True))]
CreatedAt = Annotated[
    datetime,
    mapped_column(sa.DateTime(timezone=True), server_default=sa.func.statement_timestamp()),
]
UpdatedAt = Annotated[
    datetime,
    mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.statement_timestamp(),
        onupdate=sa.func.statement_timestamp(),
    ),
]


def enum_type(codes: type[StrEnum]) -> sa.Enum:
    return sa.Enum(
        codes,
        values_callable=lambda members: [item.value for item in members],
        native_enum=False,
        length=32,
    )


def allowed(column: str, codes: type[StrEnum]) -> sa.CheckConstraint:
    values = ", ".join(f"'{item.value}'" for item in codes)
    return sa.CheckConstraint(f"{column} IN ({values})", name=column)


def nonblank(column: str) -> sa.CheckConstraint:
    return sa.CheckConstraint(
        f"{column} <> '' AND {column} !~ '^[[:space:]]|[[:space:]]$'", name=f"{column}_text"
    )


def code_format(column: str) -> sa.CheckConstraint:
    return sa.CheckConstraint(f"{column} ~ '^[a-z][a-z0-9_]*$'", name=f"{column}_format")


def timestamp_order() -> sa.CheckConstraint:
    return sa.CheckConstraint("created_at <= updated_at", name="timestamp_order")


def external_identity(
    table: str, identifier: str
) -> tuple[sa.CheckConstraint, sa.CheckConstraint, sa.CheckConstraint, sa.Index]:
    return (
        sa.CheckConstraint(f"(source_system IS NULL) = ({identifier} IS NULL)", name="source_pair"),
        code_format("source_system"),
        nonblank(identifier),
        sa.Index(
            f"uq_{table}_external",
            "organization_id",
            "source_system",
            identifier,
            unique=True,
            postgresql_where=sa.text(f"{identifier} IS NOT NULL"),
        ),
    )


def scoped_fk(name: str, columns: list[str], references: list[str]) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        columns, references, name=name, onupdate="RESTRICT", ondelete="RESTRICT"
    )
