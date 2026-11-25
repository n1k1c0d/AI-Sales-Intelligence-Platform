import asyncio
import logging
from typing import Annotated
from uuid import UUID

import httpx
import pytest
from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from dealmind.api.dependencies import get_db_session
from dealmind.core.config import Settings
from dealmind.db.engine import create_database_engine
from dealmind.db.health import DatabaseHealth
from dealmind.main import create_app

from .support import docker

pytestmark = [pytest.mark.database, pytest.mark.asyncio]


async def test_probe_timeout_while_pool_is_exhausted(db_settings: Settings) -> None:
    settings = db_settings.model_copy(
        update={
            "db_pool_size": 1,
            "db_max_overflow": 0,
            "db_pool_timeout": 5,
            "db_health_timeout": 0.15,
        }
    )
    engine = create_database_engine(settings)
    health = DatabaseHealth(engine, settings.db_health_timeout, logging.getLogger("test.database"))
    try:
        async with engine.connect(), asyncio.timeout(2):
            assert not await health.check()
        assert await health.check()
    finally:
        await engine.dispose()


async def test_recovery_without_app_restart(db_settings: Settings, test_container: str) -> None:
    app = create_app(db_settings)

    @app.get("/test/session")
    async def query(session: Annotated[AsyncSession, Depends(get_db_session)]) -> int:
        row = await session.execute(text("SELECT 1"))
        return int(row.scalar_one())

    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client,
    ):
        original = app.state.database.engine
        first = await client.get("/api/v1/ready")
        assert first.status_code == 200 and first.json() == {
            "status": "ready",
            "checks": {"application": "ok", "database": "ok"},
        }
        assert UUID(first.headers["X-Request-ID"]).version == 4
        assert (await client.get("/test/session")).json() == 1
        try:
            await asyncio.to_thread(docker, "stop", "-t", "5", test_container)
            assert (await client.get("/api/v1/health")).json() == {
                "status": "ok",
                "service": "dealmind-api",
            }
            async with asyncio.timeout(6):
                failed = await client.get("/api/v1/ready")
            assert failed.status_code == 503 and failed.json() == {
                "status": "not_ready",
                "checks": {"application": "ok", "database": "not_ready"},
            }
            assert UUID(failed.headers["X-Request-ID"]).version == 4
            failure = await client.get("/test/session")
            assert failure.status_code == 503 and failure.json() == {
                "error": {
                    "code": "DATABASE_UNAVAILABLE",
                    "message": "Database unavailable",
                    "details": None,
                }
            }
            assert UUID(failure.headers["X-Request-ID"]).version == 4
        finally:
            await asyncio.to_thread(docker, "start", test_container)
        async with asyncio.timeout(45):
            while (await client.get("/api/v1/ready")).status_code != 200:
                await asyncio.sleep(0.25)
        assert original is app.state.database.engine
        assert (await client.get("/test/session")).json() == 1
