"""Acceptance against the guarded DM-007 cluster and a fresh DM-102 schema per test."""

import asyncio
import json
import os
import subprocess
import sys
from collections.abc import Iterator
from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
import sqlalchemy as sa
from psycopg import sql

from dealmind.core.config import Settings
from dealmind.demo import seeder
from dealmind.demo.config import Config
from dealmind.demo.dataset import Dataset
from dealmind.demo.generator import generate
from dealmind.demo.seeder import Conflict, UnsafeTarget, VerificationError, seed

from .support import API_DIR, migrate, sql_connection, temporary_database

pytestmark = pytest.mark.database


@pytest.fixture
def destination(db_settings: Settings) -> Iterator[Settings]:
    with temporary_database(db_settings) as settings:
        migrate(settings, "upgrade", "head")
        yield settings


@pytest.fixture
def small() -> Dataset:
    return generate(Config(deals_count=80, contacts_count=45, managers_count=3))


def cli(settings: Settings, *args: str) -> subprocess.CompletedProcess[str]:
    assert settings.db_password
    env = dict(
        os.environ,
        APP_ENV="test",
        APP_DB_HOST=settings.db_host,
        APP_DB_PORT=str(settings.db_port),
        APP_DB_NAME=settings.db_name,
        APP_DB_USER=settings.db_user,
        APP_DB_PASSWORD=settings.db_password.get_secret_value(),
    )
    return subprocess.run(
        [sys.executable, "-m", "dealmind.demo.cli", "seed", "--apply", *args],
        cwd=API_DIR,
        env=env,
        text=True,
        capture_output=True,
        timeout=120,
    )


def test_full_demo_cli_seed(destination: Settings) -> None:
    expected = json.loads(
        (API_DIR.parents[1] / "data/demo/dataset-manifest.json").read_text(encoding="utf-8")
    )
    organization, contact = uuid4(), uuid4()
    with sql_connection(destination) as conn:
        conn.execute(
            "INSERT INTO organizations (id,name,timezone,default_currency) VALUES (%s,%s,'UTC','RUB')",
            (organization, expected["organization_name"]),
        )
        conn.execute(
            "INSERT INTO contacts (id,organization_id,full_name) VALUES (%s,%s,'Unrelated fixture')",
            (contact, organization),
        )
        original = conn.execute(
            "SELECT * FROM organizations WHERE id=%s", (organization,)
        ).fetchone()
        old_contact = conn.execute("SELECT * FROM contacts WHERE id=%s", (contact,)).fetchone()
        for status in ("CREATED", "ALREADY_EXISTS"):
            run = cli(destination)
            assert run.returncode == 0, run.stderr
            result = json.loads(run.stdout)
            assert result["status"] == status and result["verified"] == expected["counts"]
            assert result["inserted"] == {
                k: (v if status == "CREATED" else 0) for k, v in expected["counts"].items()
            }
            assert all(result[k] == v for k, v in expected.items())
        clash = cli(destination, "--seed", "43")
        assert clash.returncode == 3 and "CONFLICT" in clash.stderr
        assert (
            conn.execute("SELECT * FROM organizations WHERE id=%s", (organization,)).fetchone()
            == original
        )
        assert (
            conn.execute("SELECT * FROM contacts WHERE id=%s", (contact,)).fetchone() == old_contact
        )
        for table, n in expected["counts"].items():
            extra = int(table in ("organizations", "contacts"))
            assert conn.execute(
                sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(table))
            ).fetchone() == (n + extra,)
        sums = conn.execute(
            "SELECT status,currency,sum(amount) FROM deals GROUP BY status,currency"
        ).fetchall()
        assert all(
            isinstance(total, Decimal) and str(total) == expected["amounts_by_currency"][s][c]
            for s, c, total in sums
        )
        for expr, key in (("owner_id::text", "deals_by_manager"), ("status", "deal_statuses")):
            query = sql.SQL("SELECT {},count(*) FROM deals GROUP BY 1").format(sql.SQL(expr))
            assert {row[0]: row[1] for row in conn.execute(query)} == expected[key]
        for statement, key in (
            (
                "SELECT s.code,count(*) FROM deals d JOIN pipeline_stages s ON d.stage_id=s.id GROUP BY 1",
                "deals_by_stage",
            ),
            (
                "SELECT loss_reason,count(*) FROM deals WHERE status='lost' GROUP BY 1",
                "loss_reasons",
            ),
            (
                "SELECT CASE WHEN next_action_at IS NULL THEN 'missing' WHEN next_action_at < %s THEN 'overdue' WHEN next_action_at = %s THEN 'due_now' ELSE 'planned' END,count(*) FROM deals WHERE status='open' GROUP BY 1",
                "open_follow_up",
            ),
        ):
            args = (expected["anchor_datetime"],) * 2 if key == "open_follow_up" else ()
            assert {r[0]: r[1] for r in conn.execute(sql.SQL(statement), args)} == expected[key]
        assert (
            conn.execute("""SELECT count(*) FROM deals d WHERE last_activity_at IS DISTINCT FROM
            (SELECT max(occurred_at) FROM activities a WHERE a.deal_id=d.id AND a.activity_type IN ('call','email','message','meeting'))""").fetchone()
            == (0,)
        )
        assert conn.execute(
            """SELECT count(*) FILTER (WHERE direction!='internal'),count(*) FILTER (WHERE direction='internal') FROM activities"""
        ).fetchone() == (expected["meaningful_activities"], expected["internal_activities"])
        assert (
            conn.execute("""WITH steps AS (SELECT h.*,row_number() OVER w AS n,lag(to_stage_id) OVER w AS prev,
            lag(changed_at) OVER w AS prev_time FROM deal_stage_history h WINDOW w AS (PARTITION BY deal_id ORDER BY sequence_no))
            SELECT count(*) FROM steps WHERE sequence_no<>n OR from_stage_id IS DISTINCT FROM prev OR changed_at<prev_time""").fetchone()
            == (0,)
        )
        assert conn.execute(
            "SELECT count(DISTINCT deal_id) FROM (SELECT deal_id,to_stage_id FROM deal_stage_history GROUP BY 1,2 HAVING count(*)>1) r"
        ).fetchone() == (expected["deals_with_stage_reentry"],)
        assert conn.execute(
            "SELECT changed_at FROM deal_stage_history WHERE deal_id=%s ORDER BY sequence_no DESC LIMIT 1",
            (expected["scenario_deals"]["B-D14"],),
        ).fetchone() == (Config().anchor_datetime - timedelta(days=14),)
        assert conn.execute("SELECT version_num FROM alembic_version").fetchone() == ("0002",)


@pytest.mark.asyncio
async def test_demo_concurrent_and_modified(destination: Settings, small: Dataset) -> None:
    results = await asyncio.gather(
        seed(small, destination, apply=True), seed(small, destination, apply=True)
    )
    assert sorted(r.status for r in results) == ["ALREADY_EXISTS", "CREATED"]
    assert all(r.verified == small.counts() for r in results)
    with sql_connection(destination) as conn:
        conn.execute("UPDATE deals SET title='Changed locally' WHERE id=%s", (small.deals[0].id,))
        with pytest.raises(Conflict, match="deals"):
            await seed(small, destination, apply=True)
        assert conn.execute(
            "SELECT title FROM deals WHERE id=%s", (small.deals[0].id,)
        ).fetchone() == ("Changed locally",)


@pytest.mark.asyncio
async def test_demo_partial_conflict(destination: Settings, small: Dataset) -> None:
    org = small.organizations[0]
    with sql_connection(destination) as conn:
        conn.execute(
            "INSERT INTO organizations (id,name,timezone,default_currency,is_active,created_at,updated_at) VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (
                org.id,
                org.name,
                org.timezone,
                org.default_currency,
                org.is_active,
                org.created_at,
                org.updated_at,
            ),
        )
        with pytest.raises(Conflict, match="users"):
            await seed(small, destination, apply=True)
        assert conn.execute("SELECT count(*) FROM users").fetchone() == (0,)


@pytest.mark.asyncio
async def test_demo_persistence_rollback(destination: Settings, small: Dataset) -> None:
    with sql_connection(destination) as conn:
        # Fail a real INSERT only after six earlier tables have been populated.
        conn.execute("ALTER TABLE activities ADD CONSTRAINT reject_fixture CHECK (false)")
        with pytest.raises(sa.exc.IntegrityError):
            await seed(small, destination, apply=True)
        for name in small.counts():
            assert conn.execute(
                sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(name))
            ).fetchone() == (0,)


@pytest.mark.asyncio
async def test_demo_revision_and_postcommit_failure(
    db_settings: Settings, small: Dataset, monkeypatch: pytest.MonkeyPatch
) -> None:
    with temporary_database(db_settings) as settings:
        migrate(settings, "upgrade", "0001")
        with pytest.raises(UnsafeTarget, match="revision"):
            await seed(small, settings, apply=True)
        migrate(settings, "upgrade", "head")

        async def fail_verification(*args: object) -> dict[str, int]:
            raise sa.exc.SQLAlchemyError("fixture")

        with monkeypatch.context() as patch:
            patch.setattr(seeder, "compare_rows", fail_verification)
            with pytest.raises(VerificationError, match="post-commit"):
                await seed(small, settings, apply=True)
        result = await seed(small, settings, apply=True)
        assert result.status == "ALREADY_EXISTS" and result.verified == small.counts()
