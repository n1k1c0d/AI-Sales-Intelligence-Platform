from importlib.metadata import version

from fastapi.testclient import TestClient


def test_openapi_contract(client: TestClient) -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert schema["openapi"].startswith("3.")
    assert schema["info"]["title"] == "DealMind API"
    assert schema["info"]["version"] == version("dealmind-api")
    assert schema["info"]["description"]
    assert set(schema["paths"]) == {"/api/v1/health", "/api/v1/ready"}

    checks = schema["components"]["schemas"]["ReadinessChecks"]
    assert set(checks["required"]) == {"application", "database"}

    for path, model in [
        ("/api/v1/health", "HealthResponse"),
        ("/api/v1/ready", "ReadinessResponse"),
    ]:
        operation = schema["paths"][path]["get"]
        assert operation["tags"] == ["System"]
        assert operation["summary"] and operation["description"]
        responses = operation["responses"]
        statuses = ["200", "503"] if path.endswith("/ready") else ["200"]
        for status in statuses:
            shape = responses[status]["content"]["application/json"]["schema"]
            assert shape["$ref"] == f"#/components/schemas/{model}"
        assert model in schema["components"]["schemas"]
        for status in ("422", "500"):
            assert responses[status]["content"]["application/json"]["schema"]["$ref"] == (
                "#/components/schemas/ErrorResponse"
            )


def test_swagger_ui(client: TestClient) -> None:
    response = client.get("/docs")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "SwaggerUIBundle" in response.text and "/openapi.json" in response.text
