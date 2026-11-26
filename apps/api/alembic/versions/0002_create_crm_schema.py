"""Create the eight CRM tables. Downgrade discards their data."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("default_currency", sa.String(length=3), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("statement_timestamp()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("statement_timestamp()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "default_currency ~ '^[A-Z]{3}$'", name=op.f("ck_organizations_currency_format")
        ),
        sa.CheckConstraint(
            "name <> '' AND name !~ '^[[:space:]]|[[:space:]]$'",
            name=op.f("ck_organizations_name_text"),
        ),
        sa.CheckConstraint(
            "created_at <= updated_at", name=op.f("ck_organizations_timestamp_order")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_organizations")),
    )
    op.create_table(
        "contacts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=True),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("source_system", sa.String(length=64), nullable=True),
        sa.Column("external_id", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("statement_timestamp()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("statement_timestamp()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "external_id <> '' AND external_id !~ '^[[:space:]]|[[:space:]]$'",
            name=op.f("ck_contacts_external_id_text"),
        ),
        sa.CheckConstraint(
            "full_name <> '' AND full_name !~ '^[[:space:]]|[[:space:]]$'",
            name=op.f("ck_contacts_full_name_text"),
        ),
        sa.CheckConstraint(
            "source_system ~ '^[a-z][a-z0-9_]*$'", name=op.f("ck_contacts_source_system_format")
        ),
        sa.CheckConstraint(
            "(source_system IS NULL) = (external_id IS NULL)", name=op.f("ck_contacts_source_pair")
        ),
        sa.CheckConstraint("created_at <= updated_at", name=op.f("ck_contacts_timestamp_order")),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_contacts_organization_id_organizations"),
            onupdate="RESTRICT",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_contacts")),
        sa.UniqueConstraint("organization_id", "id", name="uq_contacts_org_id"),
    )
    op.create_index(
        "uq_contacts_external",
        "contacts",
        ["organization_id", "source_system", "external_id"],
        unique=True,
        postgresql_where=sa.text("external_id IS NOT NULL"),
    )
    op.create_table(
        "pipelines",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("statement_timestamp()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("statement_timestamp()"),
            nullable=False,
        ),
        sa.CheckConstraint("code ~ '^[a-z][a-z0-9_]*$'", name=op.f("ck_pipelines_code_format")),
        sa.CheckConstraint(
            "name <> '' AND name !~ '^[[:space:]]|[[:space:]]$'",
            name=op.f("ck_pipelines_name_text"),
        ),
        sa.CheckConstraint("created_at <= updated_at", name=op.f("ck_pipelines_timestamp_order")),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_pipelines_organization_id_organizations"),
            onupdate="RESTRICT",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pipelines")),
        sa.UniqueConstraint("organization_id", "code", name="uq_pipelines_org_code"),
        sa.UniqueConstraint("organization_id", "id", name="uq_pipelines_org_id"),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=True),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("statement_timestamp()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("statement_timestamp()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "email = lower(email) AND email <> '' AND email !~ '[[:space:]]' AND octet_length(email) = char_length(email)",
            name=op.f("ck_users_email_canonical"),
        ),
        sa.CheckConstraint(
            "full_name <> '' AND full_name !~ '^[[:space:]]|[[:space:]]$'",
            name=op.f("ck_users_full_name_text"),
        ),
        sa.CheckConstraint(
            "role IN ('manager', 'sales_lead', 'admin')", name=op.f("ck_users_role")
        ),
        sa.CheckConstraint("created_at <= updated_at", name=op.f("ck_users_timestamp_order")),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_users_organization_id_organizations"),
            onupdate="RESTRICT",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("organization_id", "id", name="uq_users_org_id"),
    )
    op.create_index(
        "uq_users_org_email",
        "users",
        ["organization_id", "email"],
        unique=True,
        postgresql_where=sa.text("email IS NOT NULL"),
    )
    op.create_table(
        "pipeline_stages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("pipeline_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("stage_type", sa.String(length=32), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("statement_timestamp()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("statement_timestamp()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "code ~ '^[a-z][a-z0-9_]*$'", name=op.f("ck_pipeline_stages_code_format")
        ),
        sa.CheckConstraint(
            "name <> '' AND name !~ '^[[:space:]]|[[:space:]]$'",
            name=op.f("ck_pipeline_stages_name_text"),
        ),
        sa.CheckConstraint(
            "stage_type IN ('open', 'won', 'lost')", name=op.f("ck_pipeline_stages_stage_type")
        ),
        sa.CheckConstraint(
            "created_at <= updated_at", name=op.f("ck_pipeline_stages_timestamp_order")
        ),
        sa.CheckConstraint("position >= 0", name=op.f("ck_pipeline_stages_position")),
        sa.ForeignKeyConstraint(
            ["organization_id", "pipeline_id"],
            ["pipelines.organization_id", "pipelines.id"],
            name="fk_stages_pipeline",
            onupdate="RESTRICT",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_pipeline_stages_organization_id_organizations"),
            onupdate="RESTRICT",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pipeline_stages")),
        sa.UniqueConstraint(
            "organization_id", "pipeline_id", "id", "stage_type", name="uq_stages_scope_id_type"
        ),
        sa.UniqueConstraint("organization_id", "pipeline_id", "id", name="uq_stages_scope_id"),
        sa.UniqueConstraint("pipeline_id", "code", name="uq_stages_pipeline_code"),
        sa.UniqueConstraint("pipeline_id", "position", name="uq_stages_pipeline_position"),
    )
    op.create_index(
        "uq_stages_terminal",
        "pipeline_stages",
        ["pipeline_id", "stage_type"],
        unique=True,
        postgresql_where=sa.text("stage_type IN ('won','lost')"),
    )
    op.create_table(
        "deals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("contact_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("pipeline_id", sa.Uuid(), nullable=False),
        sa.Column("stage_id", sa.Uuid(), nullable=False),
        sa.Column("source_system", sa.String(length=64), nullable=True),
        sa.Column("external_id", sa.String(length=255), nullable=True),
        sa.Column("title", sa.String(length=250), nullable=False),
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("loss_reason", sa.String(length=32), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("statement_timestamp()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("statement_timestamp()"),
            nullable=False,
        ),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_action_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "(status = 'lost') = (loss_reason IS NOT NULL)", name=op.f("ck_deals_loss")
        ),
        sa.CheckConstraint(
            "(status = 'open') = (closed_at IS NULL)", name=op.f("ck_deals_closure")
        ),
        sa.CheckConstraint(
            "amount >= 0 AND amount <> 'NaN'::numeric", name=op.f("ck_deals_amount")
        ),
        sa.CheckConstraint("currency ~ '^[A-Z]{3}$'", name=op.f("ck_deals_currency_format")),
        sa.CheckConstraint(
            "external_id <> '' AND external_id !~ '^[[:space:]]|[[:space:]]$'",
            name=op.f("ck_deals_external_id_text"),
        ),
        sa.CheckConstraint(
            "loss_reason IN ('price', 'no_budget', 'no_response', 'not_interested', 'competitor', 'timing', 'product_mismatch', 'other')",
            name=op.f("ck_deals_loss_reason"),
        ),
        sa.CheckConstraint(
            "source_system ~ '^[a-z][a-z0-9_]*$'", name=op.f("ck_deals_source_system_format")
        ),
        sa.CheckConstraint("status <> 'won' OR amount > 0", name=op.f("ck_deals_won_amount")),
        sa.CheckConstraint(
            "status = 'open' OR next_action_at IS NULL", name=op.f("ck_deals_closed_plan")
        ),
        sa.CheckConstraint("status IN ('open', 'won', 'lost')", name=op.f("ck_deals_status")),
        sa.CheckConstraint(
            "title <> '' AND title !~ '^[[:space:]]|[[:space:]]$'", name=op.f("ck_deals_title_text")
        ),
        sa.CheckConstraint(
            "(source_system IS NULL) = (external_id IS NULL)", name=op.f("ck_deals_source_pair")
        ),
        sa.CheckConstraint("closed_at >= created_at", name=op.f("ck_deals_closed_time")),
        sa.CheckConstraint("created_at <= updated_at", name=op.f("ck_deals_timestamp_order")),
        sa.ForeignKeyConstraint(
            ["organization_id", "contact_id"],
            ["contacts.organization_id", "contacts.id"],
            name="fk_deals_contact",
            onupdate="RESTRICT",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "owner_id"],
            ["users.organization_id", "users.id"],
            name="fk_deals_owner",
            onupdate="RESTRICT",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "pipeline_id", "stage_id", "status"],
            [
                "pipeline_stages.organization_id",
                "pipeline_stages.pipeline_id",
                "pipeline_stages.id",
                "pipeline_stages.stage_type",
            ],
            name="fk_deals_stage",
            onupdate="RESTRICT",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "pipeline_id"],
            ["pipelines.organization_id", "pipelines.id"],
            name="fk_deals_pipeline",
            onupdate="RESTRICT",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_deals_organization_id_organizations"),
            onupdate="RESTRICT",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_deals")),
        sa.UniqueConstraint("organization_id", "id", name="uq_deals_org_id"),
        sa.UniqueConstraint("organization_id", "pipeline_id", "id", name="uq_deals_scope_id"),
    )
    op.create_index(
        "ix_deals_org_closed",
        "deals",
        ["organization_id", "closed_at"],
        unique=False,
        postgresql_where=sa.text("closed_at IS NOT NULL"),
    )
    op.create_index(
        "ix_deals_org_created", "deals", ["organization_id", "created_at"], unique=False
    )
    op.create_index(
        "ix_deals_org_next_action",
        "deals",
        ["organization_id", "next_action_at"],
        unique=False,
        postgresql_where=sa.text("status = 'open' AND next_action_at IS NOT NULL"),
    )
    op.create_index(
        "ix_deals_org_owner_status",
        "deals",
        ["organization_id", "owner_id", "status"],
        unique=False,
    )
    op.create_index("ix_deals_org_stage", "deals", ["organization_id", "stage_id"], unique=False)
    op.create_index("ix_deals_org_status", "deals", ["organization_id", "status"], unique=False)
    op.create_index(
        "uq_deals_external",
        "deals",
        ["organization_id", "source_system", "external_id"],
        unique=True,
        postgresql_where=sa.text("external_id IS NOT NULL"),
    )
    op.create_table(
        "activities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("deal_id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("activity_type", sa.String(length=32), nullable=False),
        sa.Column("direction", sa.String(length=32), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column(
            "metadata", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("statement_timestamp()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(activity_type IN ('note','task')) = (direction = 'internal')",
            name=op.f("ck_activities_type_direction"),
        ),
        sa.CheckConstraint(
            "activity_type IN ('call', 'message', 'email', 'meeting', 'note', 'task')",
            name=op.f("ck_activities_activity_type"),
        ),
        sa.CheckConstraint(
            "direction IN ('inbound', 'outbound', 'internal')", name=op.f("ck_activities_direction")
        ),
        sa.CheckConstraint(
            "jsonb_typeof(metadata) = 'object'", name=op.f("ck_activities_metadata_object")
        ),
        sa.CheckConstraint("occurred_at <= created_at", name=op.f("ck_activities_event_time")),
        sa.ForeignKeyConstraint(
            ["organization_id", "actor_id"],
            ["users.organization_id", "users.id"],
            name="fk_activities_actor",
            onupdate="RESTRICT",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "deal_id"],
            ["deals.organization_id", "deals.id"],
            name="fk_activities_deal",
            onupdate="RESTRICT",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_activities_organization_id_organizations"),
            onupdate="RESTRICT",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_activities")),
    )
    op.create_index(
        "ix_activities_deal_occurred", "activities", ["deal_id", "occurred_at"], unique=False
    )
    op.create_index(
        "ix_activities_org_actor_occurred",
        "activities",
        ["organization_id", "actor_id", "occurred_at"],
        unique=False,
    )
    op.create_table(
        "deal_stage_history",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("deal_id", sa.Uuid(), nullable=False),
        sa.Column("pipeline_id", sa.Uuid(), nullable=False),
        sa.Column("from_stage_id", sa.Uuid(), nullable=True),
        sa.Column("to_stage_id", sa.Uuid(), nullable=False),
        sa.Column("changed_by_id", sa.Uuid(), nullable=True),
        sa.Column("sequence_no", sa.Integer(), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_system", sa.String(length=64), nullable=True),
        sa.Column("source_event_id", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("statement_timestamp()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "source_event_id <> '' AND source_event_id !~ '^[[:space:]]|[[:space:]]$'",
            name=op.f("ck_deal_stage_history_source_event_id_text"),
        ),
        sa.CheckConstraint(
            "source_system ~ '^[a-z][a-z0-9_]*$'",
            name=op.f("ck_deal_stage_history_source_system_format"),
        ),
        sa.CheckConstraint(
            "(sequence_no = 1) = (from_stage_id IS NULL)",
            name=op.f("ck_deal_stage_history_first_stage"),
        ),
        sa.CheckConstraint(
            "(source_system IS NULL) = (source_event_id IS NULL)",
            name=op.f("ck_deal_stage_history_source_pair"),
        ),
        sa.CheckConstraint(
            "changed_at <= created_at", name=op.f("ck_deal_stage_history_change_time")
        ),
        sa.CheckConstraint(
            "from_stage_id <> to_stage_id", name=op.f("ck_deal_stage_history_stage_change")
        ),
        sa.CheckConstraint(
            "sequence_no >= 1", name=op.f("ck_deal_stage_history_sequence_positive")
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "changed_by_id"],
            ["users.organization_id", "users.id"],
            name="fk_history_actor",
            onupdate="RESTRICT",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "pipeline_id", "deal_id"],
            ["deals.organization_id", "deals.pipeline_id", "deals.id"],
            name="fk_history_deal",
            onupdate="RESTRICT",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "pipeline_id", "from_stage_id"],
            [
                "pipeline_stages.organization_id",
                "pipeline_stages.pipeline_id",
                "pipeline_stages.id",
            ],
            name="fk_history_from_stage",
            onupdate="RESTRICT",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "pipeline_id", "to_stage_id"],
            [
                "pipeline_stages.organization_id",
                "pipeline_stages.pipeline_id",
                "pipeline_stages.id",
            ],
            name="fk_history_to_stage",
            onupdate="RESTRICT",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_deal_stage_history_organization_id_organizations"),
            onupdate="RESTRICT",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_deal_stage_history")),
        sa.UniqueConstraint("deal_id", "sequence_no", name="uq_history_deal_seq"),
    )
    op.create_index(
        "ix_history_deal_changed_seq",
        "deal_stage_history",
        ["deal_id", "changed_at", "sequence_no"],
        unique=False,
    )
    op.create_index(
        "uq_deal_stage_history_external",
        "deal_stage_history",
        ["organization_id", "source_system", "source_event_id"],
        unique=True,
        postgresql_where=sa.text("source_event_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_table("deal_stage_history")
    op.drop_table("activities")
    op.drop_table("deals")
    op.drop_table("pipeline_stages")
    op.drop_table("users")
    op.drop_table("pipelines")
    op.drop_table("contacts")
    op.drop_table("organizations")
