from uuid import UUID

from fastapi.testclient import TestClient

from dealmind.core.config import Settings
from dealmind.main import create_app


def test_allowlist_and_browser_access_to_id() -> None:
    app = create_app(Settings(cors_origins=("https://ui.example",)))
    with TestClient(app) as client:
        allowed = client.get("/api/v1/health", headers={"Origin": "https://ui.example"})
        assert allowed.headers["access-control-allow-origin"] == "https://ui.example"
        assert "x-request-id" in allowed.headers["access-control-expose-headers"].lower()
        assert "access-control-allow-credentials" not in allowed.headers
        denied = client.get("/api/v1/health", headers={"Origin": "https://elsewhere.example"})
        assert "access-control-allow-origin" not in denied.headers
        assert UUID(denied.headers["x-request-id"]).version == 4


def test_preflight_and_default_closed_policy() -> None:
    headers = {
        "Origin": "http://localhost:3000",
        "Access-Control-Request-Method": "PATCH",
        "Access-Control-Request-Headers": "Content-Type, Authorization, X-Request-ID",
    }
    for settings, status in [
        (Settings(), 400),
        (Settings(cors_origins=("http://localhost:3000",)), 200),
    ]:
        with TestClient(create_app(settings)) as client:
            response = client.options("/api/v1/health", headers=headers)
            assert response.status_code == status
            assert UUID(response.headers["x-request-id"]).version == 4
            if status == 200:
                assert response.headers["access-control-allow-origin"] == headers["Origin"]
                assert "PATCH" in response.headers["access-control-allow-methods"]
                permitted = response.headers["access-control-allow-headers"].lower()
                assert all(
                    name in permitted for name in ("authorization", "content-type", "x-request-id")
                )
            else:
                assert "access-control-allow-origin" not in response.headers
