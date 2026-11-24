import asyncio
import json
import os
import subprocess
from collections.abc import AsyncIterator, Callable

import pytest
import pytest_asyncio
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncEngine

from dealmind.core.config import Settings
from dealmind.db.engine import create_database_engine

from .support import COMPOSE, PROJECT, docker, sql_connection


def pytest_asyncio_loop_factories() -> dict[str, Callable[[], asyncio.AbstractEventLoop]]:
    return {"selector": asyncio.SelectorEventLoop}


@pytest.fixture(scope="session")
def test_container(pytestconfig: pytest.Config) -> str:
    if pytestconfig.option.markexpr != "database":
        pytest.fail("Use -m database explicitly for the isolated PostgreSQL suite")
    try:
        cid = docker("compose", "-p", PROJECT, "-f", str(COMPOSE), "ps", "-q", "postgres-test")
    except (OSError, subprocess.SubprocessError) as error:
        pytest.fail(f"Cannot inspect the isolated Compose project: {type(error).__name__}")
    if not cid:
        pytest.fail("Start the dealmind-db-test Compose project with up -d --wait first")
    # Inspect only non-secret fields. Verify the volume used for the data directory.
    labels = json.loads(docker("inspect", "--format", "{{json .Config.Labels}}", cid))
    assert labels["com.docker.compose.project"] == PROJECT
    assert labels["com.docker.compose.service"] == "postgres-test"
    mounts = json.loads(docker("inspect", "--format", "{{json .Mounts}}", cid))
    (data,) = [m for m in mounts if m["Destination"] == "/var/lib/postgresql/data"]
    assert data["Type"] == "volume" and data["Name"] == PROJECT + "_test_postgres_data"
    owner = docker(
        "volume",
        "inspect",
        "--format",
        '{{index .Labels "com.docker.compose.project"}}',
        data["Name"],
    )
    assert owner == PROJECT
    return cid


@pytest.fixture(scope="session")
def db_settings(test_container: str) -> Settings:
    config = Settings(
        env="test",
        db_host=os.getenv("DEALMIND_TEST_DB_HOST", "127.0.0.1"),
        db_port=int(os.getenv("DEALMIND_TEST_DB_PORT", "55433")),
        db_user=os.getenv("DEALMIND_TEST_DB_USER", "dealmind_test"),
        db_name=os.getenv("DEALMIND_TEST_DB_NAME", "dealmind_test"),
        db_password=SecretStr(os.getenv("DEALMIND_TEST_DB_PASSWORD", "dealmind-test-only")),
        db_connect_timeout=2,
        db_health_timeout=2,
    )
    assert config.db_host == "127.0.0.1" and config.db_name == config.db_user == "dealmind_test"
    assert docker("port", test_container, "5432/tcp") == f"127.0.0.1:{config.db_port}"
    identity = "SELECT current_database(), system_identifier FROM pg_control_system()"
    expected = docker(
        "exec",
        test_container,
        "psql",
        "-XAt",
        "-U",
        config.db_user,
        "-d",
        config.db_name,
        "-c",
        identity,
    )
    with sql_connection(config) as admin:
        row = admin.execute(identity).fetchone()
        assert row and row[0] == "dealmind_test" and f"{row[0]}|{row[1]}" == expected
    return config


@pytest_asyncio.fixture
async def engine(db_settings: Settings) -> AsyncIterator[AsyncEngine]:
    engine = create_database_engine(db_settings)
    try:
        yield engine
    finally:
        await engine.dispose()
