"""CRM storage mappings. Scoped navigation follows the complete database foreign keys."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from dealmind.db.base import Base

from ._schema import (
    CreatedAt,
    Instant,
    OrganizationId,
    PrimaryId,
    UpdatedAt,
    allowed,
    code_format,
    enum_type,
    external_identity,
    nonblank,
    scoped_fk,
    timestamp_order,
)
from .enums import ActivityDirection, ActivityType, DealStatus, LossReason, StageType, UserRole


class Organization(Base):
    __tablename__ = "organizations"
    __table_args__ = (
        nonblank("name"),
        sa.CheckConstraint("default_currency ~ '^[A-Z]{3}$'", name="currency_format"),
        timestamp_order(),
    )

    id: Mapped[PrimaryId]
    name: Mapped[str] = mapped_column(sa.String(200))
    timezone: Mapped[str] = mapped_column(sa.String(64))
    default_currency: Mapped[str] = mapped_column(sa.String(3))
    is_active: Mapped[bool] = mapped_column(server_default=sa.true())
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        sa.UniqueConstraint("organization_id", "id", name="uq_users_org_id"),
        nonblank("full_name"),
        sa.CheckConstraint(
            "email = lower(email) AND email <> '' AND email !~ '[[:space:]]' AND octet_length(email) = char_length(email)",
            name="email_canonical",
        ),
        sa.Index(
            "uq_users_org_email",
            "organization_id",
            "email",
            unique=True,
            postgresql_where=sa.text("email IS NOT NULL"),
        ),
        allowed("role", UserRole),
        timestamp_order(),
    )

    id: Mapped[PrimaryId]
    organization_id: Mapped[OrganizationId]
    full_name: Mapped[str] = mapped_column(sa.String(200))
    email: Mapped[str | None] = mapped_column(sa.String(254))
    role: Mapped[UserRole] = mapped_column(enum_type(UserRole))
    is_active: Mapped[bool] = mapped_column(server_default=sa.true())
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]


class Contact(Base):
    __tablename__ = "contacts"
    __table_args__ = (
        sa.UniqueConstraint("organization_id", "id", name="uq_contacts_org_id"),
        nonblank("full_name"),
        *external_identity("contacts", "external_id"),
        timestamp_order(),
    )

    id: Mapped[PrimaryId]
    organization_id: Mapped[OrganizationId]
    full_name: Mapped[str] = mapped_column(sa.String(200))
    email: Mapped[str | None] = mapped_column(sa.String(254))
    phone: Mapped[str | None] = mapped_column(sa.String(32))
    source_system: Mapped[str | None] = mapped_column(sa.String(64))
    external_id: Mapped[str | None] = mapped_column(sa.String(255))
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]
    deals: Mapped[list[Deal]] = relationship(back_populates="contact", lazy="raise", viewonly=True)


class Pipeline(Base):
    __tablename__ = "pipelines"
    __table_args__ = (
        sa.UniqueConstraint("organization_id", "id", name="uq_pipelines_org_id"),
        sa.UniqueConstraint("organization_id", "code", name="uq_pipelines_org_code"),
        nonblank("name"),
        code_format("code"),
        timestamp_order(),
    )

    id: Mapped[PrimaryId]
    organization_id: Mapped[OrganizationId]
    name: Mapped[str] = mapped_column(sa.String(150))
    code: Mapped[str] = mapped_column(sa.String(64))
    description: Mapped[str | None] = mapped_column(sa.Text)
    is_active: Mapped[bool] = mapped_column(server_default=sa.false())
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]
    stages: Mapped[list[PipelineStage]] = relationship(
        back_populates="pipeline", order_by="PipelineStage.position", lazy="raise", viewonly=True
    )


class PipelineStage(Base):
    __tablename__ = "pipeline_stages"
    __table_args__ = (
        scoped_fk(
            "fk_stages_pipeline",
            ["organization_id", "pipeline_id"],
            ["pipelines.organization_id", "pipelines.id"],
        ),
        sa.UniqueConstraint("organization_id", "pipeline_id", "id", name="uq_stages_scope_id"),
        sa.UniqueConstraint(
            "organization_id", "pipeline_id", "id", "stage_type", name="uq_stages_scope_id_type"
        ),
        sa.UniqueConstraint("pipeline_id", "code", name="uq_stages_pipeline_code"),
        sa.UniqueConstraint("pipeline_id", "position", name="uq_stages_pipeline_position"),
        sa.Index(
            "uq_stages_terminal",
            "pipeline_id",
            "stage_type",
            unique=True,
            postgresql_where=sa.text("stage_type IN ('won','lost')"),
        ),
        nonblank("name"),
        code_format("code"),
        sa.CheckConstraint("position >= 0", name="position"),
        allowed("stage_type", StageType),
        timestamp_order(),
    )

    id: Mapped[PrimaryId]
    organization_id: Mapped[OrganizationId]
    pipeline_id: Mapped[UUID]
    name: Mapped[str] = mapped_column(sa.String(150))
    code: Mapped[str] = mapped_column(sa.String(64))
    position: Mapped[int]
    stage_type: Mapped[StageType] = mapped_column(enum_type(StageType))
    is_active: Mapped[bool] = mapped_column(server_default=sa.true())
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]
    pipeline: Mapped[Pipeline] = relationship(back_populates="stages", lazy="raise", viewonly=True)


class Deal(Base):
    __tablename__ = "deals"
    __table_args__ = (
        scoped_fk(
            "fk_deals_contact",
            ["organization_id", "contact_id"],
            ["contacts.organization_id", "contacts.id"],
        ),
        scoped_fk(
            "fk_deals_owner", ["organization_id", "owner_id"], ["users.organization_id", "users.id"]
        ),
        scoped_fk(
            "fk_deals_pipeline",
            ["organization_id", "pipeline_id"],
            ["pipelines.organization_id", "pipelines.id"],
        ),
        scoped_fk(
            "fk_deals_stage",
            ["organization_id", "pipeline_id", "stage_id", "status"],
            [
                "pipeline_stages.organization_id",
                "pipeline_stages.pipeline_id",
                "pipeline_stages.id",
                "pipeline_stages.stage_type",
            ],
        ),
        sa.UniqueConstraint("organization_id", "id", name="uq_deals_org_id"),
        sa.UniqueConstraint("organization_id", "pipeline_id", "id", name="uq_deals_scope_id"),
        *external_identity("deals", "external_id"),
        nonblank("title"),
        allowed("status", DealStatus),
        allowed("loss_reason", LossReason),
        sa.CheckConstraint("amount >= 0 AND amount <> 'NaN'::numeric", name="amount"),
        sa.CheckConstraint("status <> 'won' OR amount > 0", name="won_amount"),
        sa.CheckConstraint("currency ~ '^[A-Z]{3}$'", name="currency_format"),
        sa.CheckConstraint("(status = 'open') = (closed_at IS NULL)", name="closure"),
        sa.CheckConstraint("(status = 'lost') = (loss_reason IS NOT NULL)", name="loss"),
        sa.CheckConstraint("status = 'open' OR next_action_at IS NULL", name="closed_plan"),
        sa.CheckConstraint("closed_at >= created_at", name="closed_time"),
        timestamp_order(),
        sa.Index("ix_deals_org_status", "organization_id", "status"),
        sa.Index("ix_deals_org_owner_status", "organization_id", "owner_id", "status"),
        sa.Index("ix_deals_org_stage", "organization_id", "stage_id"),
        sa.Index("ix_deals_org_created", "organization_id", "created_at"),
        sa.Index(
            "ix_deals_org_closed",
            "organization_id",
            "closed_at",
            postgresql_where=sa.text("closed_at IS NOT NULL"),
        ),
        sa.Index(
            "ix_deals_org_next_action",
            "organization_id",
            "next_action_at",
            postgresql_where=sa.text("status = 'open' AND next_action_at IS NOT NULL"),
        ),
    )

    id: Mapped[PrimaryId]
    organization_id: Mapped[OrganizationId]
    contact_id: Mapped[UUID]
    owner_id: Mapped[UUID]
    pipeline_id: Mapped[UUID]
    stage_id: Mapped[UUID]
    source_system: Mapped[str | None] = mapped_column(sa.String(64))
    external_id: Mapped[str | None] = mapped_column(sa.String(255))
    title: Mapped[str] = mapped_column(sa.String(250))
    amount: Mapped[Decimal] = mapped_column(sa.Numeric(14, 2))
    currency: Mapped[str] = mapped_column(sa.String(3))
    status: Mapped[DealStatus] = mapped_column(enum_type(DealStatus))
    loss_reason: Mapped[LossReason | None] = mapped_column(enum_type(LossReason))
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]
    closed_at: Mapped[Instant | None]
    next_action_at: Mapped[Instant | None]
    last_activity_at: Mapped[Instant | None]
    contact: Mapped[Contact] = relationship(back_populates="deals", lazy="raise", viewonly=True)
    owner: Mapped[User] = relationship(lazy="raise", viewonly=True)
    pipeline: Mapped[Pipeline] = relationship(lazy="raise", viewonly=True)
    stage: Mapped[PipelineStage] = relationship(lazy="raise", viewonly=True)
    activities: Mapped[list[Activity]] = relationship(
        back_populates="deal", lazy="raise", viewonly=True
    )
    stage_history: Mapped[list[DealStageHistory]] = relationship(
        back_populates="deal", order_by="DealStageHistory.sequence_no", lazy="raise", viewonly=True
    )


class Activity(Base):
    __tablename__ = "activities"
    __table_args__ = (
        scoped_fk(
            "fk_activities_deal",
            ["organization_id", "deal_id"],
            ["deals.organization_id", "deals.id"],
        ),
        scoped_fk(
            "fk_activities_actor",
            ["organization_id", "actor_id"],
            ["users.organization_id", "users.id"],
        ),
        allowed("activity_type", ActivityType),
        allowed("direction", ActivityDirection),
        sa.CheckConstraint(
            "(activity_type IN ('note','task')) = (direction = 'internal')", name="type_direction"
        ),
        sa.CheckConstraint("jsonb_typeof(metadata) = 'object'", name="metadata_object"),
        sa.CheckConstraint("occurred_at <= created_at", name="event_time"),
        sa.Index("ix_activities_deal_occurred", "deal_id", "occurred_at"),
        sa.Index("ix_activities_org_actor_occurred", "organization_id", "actor_id", "occurred_at"),
    )

    id: Mapped[PrimaryId]
    organization_id: Mapped[OrganizationId]
    deal_id: Mapped[UUID]
    actor_id: Mapped[UUID | None]
    activity_type: Mapped[ActivityType] = mapped_column(enum_type(ActivityType))
    direction: Mapped[ActivityDirection] = mapped_column(enum_type(ActivityDirection))
    occurred_at: Mapped[Instant]
    summary: Mapped[str | None] = mapped_column(sa.Text)
    metadata_: Mapped[dict[str, object]] = mapped_column(
        "metadata", JSONB, default=dict, server_default=sa.text("'{}'::jsonb")
    )
    created_at: Mapped[CreatedAt]
    actor: Mapped[User | None] = relationship(lazy="raise", viewonly=True)
    deal: Mapped[Deal] = relationship(back_populates="activities", lazy="raise", viewonly=True)


class DealStageHistory(Base):
    __tablename__ = "deal_stage_history"
    __table_args__ = (
        scoped_fk(
            "fk_history_deal",
            ["organization_id", "pipeline_id", "deal_id"],
            ["deals.organization_id", "deals.pipeline_id", "deals.id"],
        ),
        scoped_fk(
            "fk_history_from_stage",
            ["organization_id", "pipeline_id", "from_stage_id"],
            [
                "pipeline_stages.organization_id",
                "pipeline_stages.pipeline_id",
                "pipeline_stages.id",
            ],
        ),
        scoped_fk(
            "fk_history_to_stage",
            ["organization_id", "pipeline_id", "to_stage_id"],
            [
                "pipeline_stages.organization_id",
                "pipeline_stages.pipeline_id",
                "pipeline_stages.id",
            ],
        ),
        scoped_fk(
            "fk_history_actor",
            ["organization_id", "changed_by_id"],
            ["users.organization_id", "users.id"],
        ),
        sa.UniqueConstraint("deal_id", "sequence_no", name="uq_history_deal_seq"),
        sa.CheckConstraint("sequence_no >= 1", name="sequence_positive"),
        sa.CheckConstraint("(sequence_no = 1) = (from_stage_id IS NULL)", name="first_stage"),
        sa.CheckConstraint("from_stage_id <> to_stage_id", name="stage_change"),
        sa.CheckConstraint("changed_at <= created_at", name="change_time"),
        *external_identity("deal_stage_history", "source_event_id"),
        sa.Index("ix_history_deal_changed_seq", "deal_id", "changed_at", "sequence_no"),
    )

    id: Mapped[PrimaryId]
    organization_id: Mapped[OrganizationId]
    deal_id: Mapped[UUID]
    pipeline_id: Mapped[UUID]
    from_stage_id: Mapped[UUID | None]
    to_stage_id: Mapped[UUID]
    changed_by_id: Mapped[UUID | None]
    sequence_no: Mapped[int]
    changed_at: Mapped[Instant]
    source_system: Mapped[str | None] = mapped_column(sa.String(64))
    source_event_id: Mapped[str | None] = mapped_column(sa.String(255))
    created_at: Mapped[CreatedAt]
    deal: Mapped[Deal] = relationship(back_populates="stage_history", lazy="raise", viewonly=True)
    from_stage: Mapped[PipelineStage | None] = relationship(
        foreign_keys=lambda: [
            DealStageHistory.organization_id,
            DealStageHistory.pipeline_id,
            DealStageHistory.from_stage_id,
        ],
        lazy="raise",
        viewonly=True,
    )
    to_stage: Mapped[PipelineStage] = relationship(
        foreign_keys=lambda: [
            DealStageHistory.organization_id,
            DealStageHistory.pipeline_id,
            DealStageHistory.to_stage_id,
        ],
        lazy="raise",
        viewonly=True,
    )
    changed_by: Mapped[User | None] = relationship(lazy="raise", viewonly=True)
