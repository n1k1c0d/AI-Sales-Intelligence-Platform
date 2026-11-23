import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from dealmind.api.dependencies import is_application_ready
from dealmind.main import create_app


def test_ready_after_startup(client: TestClient) -> None:
    response = client.get("/api/v1/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "checks": {"application": "ok"}}


def test_readiness_override_is_scoped(
    app: FastAPI, client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    with monkeypatch.context() as overrides:
        overrides.setitem(app.dependency_overrides, is_application_ready, lambda: False)
        response = client.get("/api/v1/ready")
        assert response.status_code == 503
        assert response.json() == {"status": "not_ready", "checks": {"application": "not_ready"}}
        assert client.get("/api/v1/health").status_code == 200
    assert client.get("/api/v1/ready").status_code == 200


def test_factory_provides_independent_lifecycles(app: FastAPI) -> None:
    other = create_app()
    assert app is not other
    assert app.dependency_overrides is not other.dependency_overrides
    assert app.state.is_ready is False
    with TestClient(app):
        assert app.state.is_ready is True
        assert other.state.is_ready is False
    assert app.state.is_ready is False
