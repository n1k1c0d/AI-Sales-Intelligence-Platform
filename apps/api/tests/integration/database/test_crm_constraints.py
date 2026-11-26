"""Exercise named PostgreSQL constraints directly, including writes that bypass the ORM."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.types.json import Jsonb

from dealmind.core.config import Settings

from .support import sql_connection

pytestmark = pytest.mark.database
type Connection = psycopg.Connection[tuple[object, ...]]

ORG, OTHER_ORG = uuid4(), uuid4()
OWNER, OTHER_OWNER = uuid4(), uuid4()
CONTACT, OTHER_CONTACT = uuid4(), uuid4()
PIPE, SECOND_PIPE, FOREIGN_PIPE = uuid4(), uuid4(), uuid4()
OPEN, NEXT, WON, LOST, SECOND_STAGE, FOREIGN_STAGE = (uuid4() for _ in range(6))
DEAL, FOREIGN_DEAL = uuid4(), uuid4()
START = datetime(2026, 1, 1, tzinfo=UTC)
LATER = START + timedelta(hours=1)
EXTERNAL = {"source_system": "crm", "external_id": "item-1"}

# Each template is a valid new row referencing the first school.
DEFAULTS: dict[str, dict[str, object]] = {
    "organizations": {"name": "Test school", "timezone": "UTC", "default_currency": "RUB"},
    "users": {"organization_id": ORG, "full_name": "Test manager", "role": "manager"},
    "contacts": {"organization_id": ORG, "full_name": "Test contact"},
    "pipelines": {"organization_id": ORG, "name": "Test pipeline", "code": "main"},
    "pipeline_stages": {
        "organization_id": ORG,
        "pipeline_id": PIPE,
        "name": "Test stage",
        "position": 90,
        "code": "extra",
        "stage_type": "open",
    },
    "deals": {
        "organization_id": ORG,
        "pipeline_id": PIPE,
        "owner_id": OWNER,
        "stage_id": OPEN,
        "contact_id": CONTACT,
        "title": "Test purchase",
        "status": "open",
        "currency": "RUB",
        "amount": Decimal("10.99"),
        "created_at": START,
    },
    "activities": {
        "organization_id": ORG,
        "deal_id": DEAL,
        "actor_id": OWNER,
        "activity_type": "note",
        "direction": "internal",
        "occurred_at": LATER,
    },
    "deal_stage_history": {
        "organization_id": ORG,
        "pipeline_id": PIPE,
        "deal_id": DEAL,
        "from_stage_id": OPEN,
        "to_stage_id": NEXT,
        "changed_by_id": OWNER,
        "sequence_no": 2,
        "changed_at": LATER,
    },
}


def insert(conn: Connection, table: str, **changes: object) -> UUID:
    values = {"id": uuid4(), **DEFAULTS[table], **changes}
    query = sql.SQL("INSERT INTO {} ({}) VALUES ({}) RETURNING id").format(
        sql.Identifier(table),
        sql.SQL(", ").join(map(sql.Identifier, values)),
        sql.SQL(", ").join(sql.Placeholder() for _ in values),
    )
    row = conn.execute(query, tuple(values.values())).fetchone()
    assert row and isinstance(row[0], UUID)
    return row[0]


@pytest.fixture(scope="module")
def reference_data(crm_settings: Settings) -> Settings:
    # Insert complete, disjoint graphs once; each case below rolls back its own writes.
    with sql_connection(crm_settings) as conn, conn.transaction():
        for org, manager, contact, pipe, first, deal in (
            (ORG, OWNER, CONTACT, PIPE, OPEN, DEAL),
            (OTHER_ORG, OTHER_OWNER, OTHER_CONTACT, FOREIGN_PIPE, FOREIGN_STAGE, FOREIGN_DEAL),
        ):
            insert(conn, "organizations", id=org)
            insert(conn, "users", id=manager, organization_id=org, email="manager@example.test")
            insert(conn, "contacts", id=contact, organization_id=org, **EXTERNAL)
            insert(conn, "pipelines", id=pipe, organization_id=org)
            for position, code, identifier, stage_type in (
                (1, "first", first, "open"),
                (2, "next", NEXT if org == ORG else uuid4(), "open"),
                (3, "won", WON if org == ORG else uuid4(), "won"),
                (4, "lost", LOST if org == ORG else uuid4(), "lost"),
            ):
                insert(
                    conn,
                    "pipeline_stages",
                    id=identifier,
                    organization_id=org,
                    pipeline_id=pipe,
                    position=position,
                    code=code,
                    stage_type=stage_type,
                )
            conn.execute("UPDATE pipelines SET is_active=true WHERE id=%s", (pipe,))
            insert(
                conn,
                "deals",
                id=deal,
                organization_id=org,
                owner_id=manager,
                contact_id=contact,
                pipeline_id=pipe,
                stage_id=first,
                **EXTERNAL,
            )
            insert(
                conn,
                "deal_stage_history",
                organization_id=org,
                deal_id=deal,
                pipeline_id=pipe,
                from_stage_id=None,
                to_stage_id=first,
                sequence_no=1,
                changed_by_id=manager,
                changed_at=START,
                source_system="crm",
                source_event_id="event-1",
            )
        insert(conn, "pipelines", id=SECOND_PIPE, code="second")
        insert(conn, "pipeline_stages", id=SECOND_STAGE, pipeline_id=SECOND_PIPE)
    return crm_settings


@pytest.fixture
def connection(reference_data: Settings) -> Iterator[Connection]:
    with sql_connection(reference_data) as conn, conn.transaction(force_rollback=True):
        yield conn


CLOSED = {"status": "won", "stage_id": WON, "closed_at": LATER}
INITIAL = {"from_stage_id": None, "sequence_no": 1}


@pytest.mark.parametrize(
    ("table", "changes", "constraint"),
    [
        pytest.param(
            "deals", {"contact_id": uuid4()}, "fk_deals_contact", id="DB-014-missing-contact"
        ),
        pytest.param(
            "deals", {"contact_id": OTHER_CONTACT}, "fk_deals_contact", id="DB-015-contact-scope"
        ),
        pytest.param("deals", {"owner_id": OTHER_OWNER}, "fk_deals_owner", id="DB-016-owner-scope"),
        pytest.param(
            "deals",
            {"pipeline_id": FOREIGN_PIPE, "stage_id": FOREIGN_STAGE},
            ("fk_deals_pipeline", "fk_deals_stage"),
            id="DB-017-pipeline-scope",
        ),
        pytest.param(
            "deals", {"stage_id": SECOND_STAGE}, "fk_deals_stage", id="DB-018-stage-pipeline"
        ),
        pytest.param(
            "deals", {"stage_id": FOREIGN_STAGE}, "fk_deals_stage", id="DB-019-stage-school"
        ),
        pytest.param(
            "activities", {"deal_id": FOREIGN_DEAL}, "fk_activities_deal", id="DB-020-activity-deal"
        ),
        pytest.param(
            "activities",
            {"actor_id": OTHER_OWNER},
            "fk_activities_actor",
            id="DB-021-activity-actor",
        ),
        pytest.param(
            "deal_stage_history",
            {"to_stage_id": SECOND_STAGE},
            "fk_history_to_stage",
            id="DB-022-to-stage",
        ),
        pytest.param(
            "deal_stage_history",
            {"from_stage_id": SECOND_STAGE},
            "fk_history_from_stage",
            id="DB-022-from-stage",
        ),
        pytest.param(
            "deal_stage_history",
            {"deal_id": FOREIGN_DEAL},
            "fk_history_deal",
            id="history-deal-scope",
        ),
        pytest.param(
            "deal_stage_history",
            {"changed_by_id": OTHER_OWNER},
            "fk_history_actor",
            id="DB-023-history-actor",
        ),
        pytest.param(
            "deals", {"amount": Decimal("-0.01")}, "ck_deals_amount", id="DB-024-negative"
        ),
        pytest.param("deals", {"amount": Decimal("NaN")}, "ck_deals_amount", id="DB-025-nan"),
        pytest.param(
            "deals",
            {"status": "invalid", "closed_at": LATER},
            "ck_deals_status",
            id="DB-026-status",
        ),
        pytest.param("deals", {"closed_at": LATER}, "ck_deals_closure", id="DB-027-open-closed"),
        pytest.param(
            "deals", {**CLOSED, "closed_at": None}, "ck_deals_closure", id="DB-028-missing-closure"
        ),
        pytest.param(
            "deals",
            {**CLOSED, "status": "lost", "stage_id": LOST},
            "ck_deals_loss",
            id="DB-029-lost-reason",
        ),
        pytest.param(
            "deals", {**CLOSED, "loss_reason": "price"}, "ck_deals_loss", id="DB-030-won-reason"
        ),
        pytest.param(
            "deals",
            {**CLOSED, "next_action_at": LATER},
            "ck_deals_closed_plan",
            id="DB-031-closed-plan",
        ),
        pytest.param(
            "deals",
            {**CLOSED, "closed_at": START - timedelta(seconds=1)},
            "ck_deals_closed_time",
            id="DB-032-closed-time",
        ),
        pytest.param("deals", {**CLOSED, "amount": 0}, "ck_deals_won_amount", id="DB-033-won-zero"),
        pytest.param("deals", {"stage_id": WON}, "fk_deals_stage", id="DB-034-stage-status"),
        pytest.param("contacts", EXTERNAL, "uq_contacts_external", id="DB-035-contact-external"),
        pytest.param("deals", EXTERNAL, "uq_deals_external", id="DB-036-deal-external"),
        pytest.param(
            "contacts",
            {"source_system": "crm"},
            "ck_contacts_source_pair",
            id="DB-039-contact-no-id",
        ),
        pytest.param(
            "deals", {"external_id": "token"}, "ck_deals_source_pair", id="DB-039-deal-no-source"
        ),
        pytest.param(
            "deal_stage_history",
            {"source_event_id": "e"},
            "ck_deal_stage_history_source_pair",
            id="DB-039-event-no-source",
        ),
        pytest.param("pipelines", {}, "uq_pipelines_org_code", id="DB-041-pipeline-code"),
        pytest.param(
            "pipeline_stages", {"code": "first"}, "uq_stages_pipeline_code", id="DB-042-stage-code"
        ),
        pytest.param(
            "pipeline_stages",
            {"position": 1},
            "uq_stages_pipeline_position",
            id="DB-043-stage-position",
        ),
        pytest.param("deal_stage_history", INITIAL, "uq_history_deal_seq", id="DB-044-sequence"),
        pytest.param(
            "deal_stage_history",
            {"source_system": "crm", "source_event_id": "event-1"},
            "uq_deal_stage_history_external",
            id="DB-045-event",
        ),
        pytest.param(
            "deal_stage_history",
            {"sequence_no": 0},
            "ck_deal_stage_history_sequence_positive",
            id="DB-046-sequence-zero",
        ),
        pytest.param(
            "deal_stage_history",
            {"sequence_no": 1},
            "ck_deal_stage_history_first_stage",
            id="DB-047-initial-from",
        ),
        pytest.param(
            "deal_stage_history",
            {"from_stage_id": None},
            "ck_deal_stage_history_first_stage",
            id="DB-048-next-no-from",
        ),
        pytest.param(
            "deal_stage_history",
            {"to_stage_id": OPEN},
            "ck_deal_stage_history_stage_change",
            id="DB-049-same-stage",
        ),
        pytest.param("users", {"role": "unknown"}, "ck_users_role", id="invalid-role"),
        pytest.param(
            "users",
            {"email": "Manager@example.test"},
            "ck_users_email_canonical",
            id="canonical-email",
        ),
        pytest.param(
            "users", {"email": "manager@example.test"}, "uq_users_org_email", id="duplicate-email"
        ),
        pytest.param(
            "organizations",
            {"default_currency": "Rub"},
            "ck_organizations_currency_format",
            id="currency",
        ),
        pytest.param("pipeline_stages", {"stage_type": "won"}, "uq_stages_terminal", id="one-won"),
        pytest.param(
            "contacts",
            {"source_system": "crm", "external_id": " x"},
            "ck_contacts_external_id_text",
            id="canonical-external",
        ),
        pytest.param(
            "activities",
            {"direction": "outbound"},
            "ck_activities_type_direction",
            id="note-direction",
        ),
        pytest.param(
            "activities",
            {"activity_type": "call"},
            "ck_activities_type_direction",
            id="call-direction",
        ),
        pytest.param(
            "activities", {"metadata": Jsonb([])}, "ck_activities_metadata_object", id="json-object"
        ),
        pytest.param(
            "deals",
            {**CLOSED, "status": "lost", "stage_id": LOST, "loss_reason": "invalid"},
            "ck_deals_loss_reason",
            id="reason-code",
        ),
    ],
)
def test_crm_constraint(
    connection: Connection,
    table: str,
    changes: dict[str, object],
    constraint: str | tuple[str, ...],
) -> None:
    with pytest.raises(psycopg.IntegrityError) as error, connection.transaction():
        insert(connection, table, **changes)
    # A foreign pipeline and its stage violate both scoped keys; PostgreSQL may report either.
    expected = (constraint,) if isinstance(constraint, str) else constraint
    assert error.value.diag.constraint_name in expected


def test_external_identity_scopes(connection: Connection) -> None:
    # DB-037, DB-038, DB-040: identical tokens across schools/sources are valid.
    for table in ("contacts", "deals"):
        rows = connection.execute(
            sql.SQL(
                "SELECT organization_id FROM {} WHERE source_system='crm' AND external_id='item-1'"
            ).format(sql.Identifier(table))
        ).fetchall()
        assert {row[0] for row in rows} == {ORG, OTHER_ORG}
        for identity in ({"source_system": "other", "external_id": "item-1"}, {}, {}):
            identifier = insert(connection, table, **identity)
            if table == "deals":
                insert(
                    connection,
                    "deal_stage_history",
                    deal_id=identifier,
                    to_stage_id=OPEN,
                    changed_at=START,
                    **INITIAL,
                )


def test_failed_transaction_is_atomic(reference_data: Settings) -> None:
    # DB-055: PostgreSQL undoes an earlier valid write in the same transaction.
    with sql_connection(reference_data) as conn:
        org = uuid4()
        with pytest.raises(psycopg.errors.ForeignKeyViolation), conn.transaction():
            insert(conn, "organizations", id=org)
            insert(conn, "deals", contact_id=uuid4())
        assert conn.execute("SELECT id FROM organizations WHERE id=%s", (org,)).fetchone() is None
