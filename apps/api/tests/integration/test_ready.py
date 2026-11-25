from typing import Annotated
from uuid import UUID

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from dealmind.api.dependencies import get_db_session, is_application_ready, is_database_ready
from dealmind.main import create_app


def test_ready_after_startup(
    client: TestClient, app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(app.dependency_overrides, is_database_ready, lambda: True)
    response = client.get("/api/v1/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "checks": {"application": "ok", "database": "ok"}}


def test_readiness_override_is_scoped(
    app: FastAPI, client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(app.dependency_overrides, is_database_ready, lambda: True)
    with monkeypatch.context() as overrides:
        overrides.setitem(app.dependency_overrides, is_application_ready, lambda: False)
        response = client.get("/api/v1/ready")
        assert response.status_code == 503
        assert response.json() == {
            "status": "not_ready",
            "checks": {"application": "not_ready", "database": "not_ready"},
        }
        assert client.get("/api/v1/health").status_code == 200
    assert client.get("/api/v1/ready").status_code == 200


def test_without_database_configuration(app: FastAPI) -> None:
    @app.get("/session")
    async def probe(session: Annotated[AsyncSession, Depends(get_db_session)]) -> bool:
        return isinstance(session, AsyncSession)

    with TestClient(app) as client:
        assert client.get("/api/v1/health").status_code == 200
        response = client.get("/api/v1/ready")
        assert response.status_code == 503
        assert response.json() == {
            "status": "not_ready",
            "checks": {"application": "ok", "database": "not_ready"},
        }
        assert UUID(response.headers["X-Request-ID"]).version == 4
        error = client.get("/session")
        assert error.status_code == 503 and error.json()["error"]["code"] == "DATABASE_UNAVAILABLE"
        assert UUID(error.headers["X-Request-ID"]).version == 4


def test_factory_provides_independent_lifecycles(app: FastAPI) -> None:
    other = create_app()
    assert app is not other
    assert app.dependency_overrides is not other.dependency_overrides
    assert app.state.is_ready is False
    with TestClient(app):
        assert app.state.is_ready is True
        assert other.state.is_ready is False
    assert app.state.is_ready is False
