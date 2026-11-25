import pytest
from fastapi.testclient import TestClient

from dealmind.main import create_app


def test_health(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.json() == {"status": "ok", "service": "dealmind-api"}


def test_health_without_external_services_or_startup(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("DATABASE_URL", "OPENAI_API_KEY", "N8N_WEBHOOK_SECRET"):
        monkeypatch.delenv(name, raising=False)
    app = create_app()
    client = TestClient(app)
    try:
        assert app.state.is_ready is False
        assert client.get("/api/v1/health").status_code == 200
        assert client.get("/api/v1/ready").status_code == 503
        assert app.state.is_ready is False
    finally:
        client.close()
