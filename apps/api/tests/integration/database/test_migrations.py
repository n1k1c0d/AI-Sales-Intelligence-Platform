from uuid import uuid4

import pytest
from psycopg import sql

from dealmind.core.config import Settings

from .support import migrate, sql_connection

pytestmark = pytest.mark.database


def test_baseline_round_trip_on_fresh_database(db_settings: Settings) -> None:
    # A fresh database on the verified test cluster also exercises extension installation.
    name = "dealmind_test_migration_" + uuid4().hex
    identifier = sql.Identifier(name)
    settings = db_settings.model_copy(update={"db_name": name})
    with sql_connection(db_settings) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(identifier))
        try:
            with sql_connection(settings) as check:
                assert check.execute("SELECT current_database()").fetchone() == (name,)
                assert (
                    check.execute(
                        "SELECT extversion FROM pg_extension WHERE extname='vector'"
                    ).fetchone()
                    is None
                )
                assert check.execute("SELECT to_regclass('public.alembic_version')").fetchone() == (
                    None,
                )
                assert migrate(settings, "heads").strip() == "0001 (head)"
                assert "0001" in migrate(settings, "history")
                migrate(settings, "upgrade", "head")
                migrate(settings, "upgrade", "head")
                assert check.execute("SELECT version_num FROM alembic_version").fetchall() == [
                    ("0001",)
                ]
                assert "0001" in migrate(settings, "current")
                assert "No new upgrade operations" in migrate(settings, "check")
                migrate(settings, "downgrade", "base")
                assert check.execute("SELECT version_num FROM alembic_version").fetchall() == []
                assert check.execute(
                    "SELECT extversion FROM pg_extension WHERE extname='vector'"
                ).fetchone() == ("0.8.7",)
                migrate(settings, "upgrade", "head")
                assert check.execute("SELECT version_num FROM alembic_version").fetchall() == [
                    ("0001",)
                ]
                row = check.execute("SELECT '[1,0,0]'::vector <-> '[0,1,0]'::vector").fetchone()
                assert row and row[0] == pytest.approx(2**0.5)
        finally:
            admin.execute(sql.SQL("DROP DATABASE {}").format(identifier))
