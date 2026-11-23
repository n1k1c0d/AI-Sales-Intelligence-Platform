from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient


def test_not_found(client: TestClient) -> None:
    response = client.get("/api/v1/nonexistent")
    assert response.status_code == 404
    assert response.json() == {
        "error": {"code": "NOT_FOUND", "message": "Resource not found", "details": None}
    }


def test_method_not_allowed(client: TestClient) -> None:
    response = client.post("/api/v1/health")
    assert response.status_code == 405
    assert "GET" in response.headers["allow"].split(", ")
    assert response.json() == {
        "error": {
            "code": "METHOD_NOT_ALLOWED",
            "message": "HTTP method is not allowed",
            "details": None,
        }
    }


def test_query_validation(app: FastAPI) -> None:
    @app.get("/probe")
    def probe(limit: int) -> int:
        return limit

    with TestClient(app) as client:
        response = client.get("/probe", params={"limit": "private-probe-value"})
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["message"] == "Request validation failed"
    (issue,) = error["details"]
    assert set(issue) == {"loc", "message", "type"}
    assert issue["loc"] == ["query", "limit"]
    assert issue["type"] == "int_parsing"
    assert issue["message"]
    assert "private-probe-value" not in response.text


def test_validation_hides_user_supplied_keys_and_values(app: FastAPI) -> None:
    @app.post("/probe")
    def probe(data: dict[str, int]) -> int:
        return len(data)

    with TestClient(app) as client:
        response = client.post("/probe", json={"private-probe-key": "private-probe-value"})
    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["loc"] == ["body"]
    assert "private-probe" not in response.text


def test_unexpected_error(app: FastAPI) -> None:
    @app.get("/probe")
    def probe() -> None:
        raise RuntimeError("internal probe diagnostic")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/probe")
    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "INTERNAL_SERVER_ERROR",
            "message": "An unexpected error occurred",
            "details": None,
        }
    }


def test_other_http_status_and_headers_are_preserved(app: FastAPI) -> None:
    @app.get("/probe")
    def probe() -> None:
        raise HTTPException(429, detail="internal probe diagnostic", headers={"Retry-After": "5"})

    with TestClient(app) as client:
        response = client.get("/probe")
    assert response.status_code == 429
    assert response.headers["retry-after"] == "5"
    assert response.json() == {
        "error": {"code": "HTTP_ERROR", "message": "HTTP request failed", "details": None}
    }
