import os
import subprocess
import sys
from pathlib import Path

import psycopg

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
