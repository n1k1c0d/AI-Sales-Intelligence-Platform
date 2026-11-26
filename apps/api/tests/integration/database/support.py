import os
import subprocess
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg import sql

from dealmind.core.config import Settings

API_DIR = Path(__file__).resolve().parents[3]
PROJECT = "dealmind-db-test"
COMPOSE = API_DIR.parents[1] / "infra/docker/postgres/compose.test.yml"


def docker(*args: str) -> str:
    return subprocess.check_output(["docker", *args], text=True, timeout=60).strip()


def sql_connection(settings: Settings) -> psycopg.Connection[tuple[object, ...]]:
    assert settings.db_password is not None
    return psycopg.connect(
        host=settings.db_host,
        port=settings.db_port,
        dbname=settings.db_name,
        user=settings.db_user,
        password=settings.db_password.get_secret_value(),
        connect_timeout=3,
        autocommit=True,
    )


@contextmanager
def temporary_database(verified: Settings) -> Iterator[Settings]:
    """Allocate a private database on the cluster verified by the db_settings fixture."""
    assert verified.env == "test" and verified.db_name == verified.db_user == "dealmind_test"
    name = "dealmind_test_crm_" + uuid4().hex
    identifier = sql.Identifier(name)
    settings = verified.model_copy(update={"db_name": name})
    with sql_connection(verified) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(identifier))
        try:
            with sql_connection(settings) as check:
                assert check.execute("SELECT current_database()").fetchone() == (name,)
            yield settings
        finally:
            admin.execute(sql.SQL("DROP DATABASE {}").format(identifier))


def migrate(settings: Settings, *args: str) -> str:
    assert settings.db_password is not None
    env = dict(
        os.environ,
        APP_ENV="test",
        APP_DB_HOST=settings.db_host,
        APP_DB_PORT=str(settings.db_port),
        APP_DB_NAME=settings.db_name,
        APP_DB_USER=settings.db_user,
        APP_DB_PASSWORD=settings.db_password.get_secret_value(),
    )
    return subprocess.check_output(
        [sys.executable, "-m", "alembic", "-c", str(API_DIR / "alembic.ini"), *args],
        env=env,
        text=True,
        timeout=30,
    )
