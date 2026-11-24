import asyncio
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import exc
from sqlalchemy.ext.asyncio import AsyncEngine

from dealmind.core.config import Settings
from dealmind.core.logging import create_app_logger
from dealmind.db.health import DatabaseHealth
from dealmind.main import create_app


@pytest.mark.asyncio
async def test_health_timeout_and_cancel(capsys: pytest.CaptureFixture[str]) -> None:
    engine = MagicMock(spec=AsyncEngine)
    connection = engine.connect.return_value

    async def wait_for_connection() -> None:
        await asyncio.Event().wait()

    connection.__aenter__.side_effect = wait_for_connection
    probe = DatabaseHealth(engine, 0.02, create_app_logger(Settings()))
    async with asyncio.timeout(1):
        assert not await probe.check()
        assert not await probe.check()
    assert capsys.readouterr().err.count("database.healthcheck.failed") == 1
    connection.__aenter__.side_effect = asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):
        await probe.check()
    connection.__aenter__.side_effect = exc.ProgrammingError(None, None, ValueError())
    with pytest.raises(exc.ProgrammingError):
        await probe.check()


def test_application_owns_engine_and_disposes_pool() -> None:
    config = Settings(db_password=SecretStr("fake-only"))
    first, second = create_app(config), create_app(config)
    with TestClient(first), TestClient(second):
        resources = first.state.database
        pool = resources.engine.pool
        assert resources.engine is not second.state.database.engine
        assert resources.sessions is not second.state.database.sessions
        assert resources.engine.sync_engine.hide_parameters and not resources.engine.echo
        assert resources.engine.pool.size() == config.db_pool_size
    assert first.state.database is None and second.state.database is None
    assert resources.engine.pool is not pool
