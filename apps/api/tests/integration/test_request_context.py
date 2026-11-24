import asyncio
import json
from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import Depends
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient
from pydantic import SecretStr

from dealmind.api.dependencies import get_settings
from dealmind.core.config import Settings
from dealmind.core.context import request_id
from dealmind.main import create_app


def test_success_and_invalid_headers(client: TestClient) -> None:
    generated = client.get("/api/v1/health").headers["X-Request-ID"]
    assert UUID(generated).version == 4
    given = str(uuid4())
    assert (
        client.get("/api/v1/ready", headers={"X-Request-ID": given.upper()}).headers["X-Request-ID"]
        == given
    )
    for supplied in ("private-probe", "00000000-0000-1000-8000-000000000000"):
        response = client.get("/api/v1/health", headers={"X-Request-ID": supplied})
        replacement = response.headers["X-Request-ID"]
        assert response.status_code == 200 and replacement != generated and replacement != supplied
        assert UUID(replacement).version == 4


def test_errors_and_completion_are_correlated_and_safe(capsys: pytest.CaptureFixture[str]) -> None:
    origin = "https://ui.example"
    app = create_app(Settings(env="test", cors_origins=(origin,)))

    @app.post("/probe/{item}")
    async def probe(item: int) -> None:
        raise RuntimeError("private-exception")

    with TestClient(app, raise_server_exceptions=False) as client:
        capsys.readouterr()  # Discard the separately tested database startup event.
        for method, path, status, route in [
            ("GET", "/api/v1/health", 200, "/api/v1/health"),
            ("GET", "/missing/private-email", 404, "<unmatched>"),
            ("DELETE", "/api/v1/ready", 405, "/api/v1/ready"),
            ("POST", "/probe/private-param", 422, "/probe/{item}"),
            ("POST", "/probe/13579", 500, "/probe/{item}"),
        ]:
            identifier = str(uuid4())
            response = client.request(
                method,
                path,
                params={"key": "private-query"},
                json={"value": "private-body"},
                headers={
                    "Authorization": "private-auth",
                    "Cookie": "s=private-cookie",
                    "X-Request-ID": identifier,
                    "Origin": origin,
                },
            )
            assert response.status_code == status
            assert response.headers["X-Request-ID"] == identifier
            assert response.headers["access-control-allow-origin"] == origin
            raw = capsys.readouterr().err
            assert "private-" not in raw and "13579" not in raw
            events = [json.loads(line) for line in raw.splitlines()]
            assert [e["event"] for e in events] == (
                ["http.request.failed"] if status == 500 else []
            ) + ["http.request.completed"]
            assert all(
                e["request_id"] == identifier
                and e["status_code"] == status
                and e["http_route"] == route
                for e in events
            )
            assert events[-1]["http_method"] == method and events[-1]["duration_ms"] >= 0
            if status == 500:
                assert events[0]["exception_type"] == "RuntimeError"
                assert response.json() == {
                    "error": {
                        "code": "INTERNAL_SERVER_ERROR",
                        "message": "An unexpected error occurred",
                        "details": None,
                    }
                }


def test_concurrent_requests_isolate_context_and_stream(capsys: pytest.CaptureFixture[str]) -> None:
    app = create_app(Settings(env="test"))
    ids = [str(uuid4()), str(uuid4())]

    async def exercise() -> None:
        barrier = asyncio.Barrier(2)

        @app.get("/stream")
        async def stream() -> StreamingResponse:
            async def chunks() -> AsyncIterator[str]:
                yield str(request_id.get())
                await barrier.wait()
                yield str(request_id.get())

            return StreamingResponse(chunks())

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:

            async def read(identifier: str) -> None:
                response = await client.get("/stream", headers={"X-Request-ID": identifier})
                assert response.text == identifier * 2
                assert response.headers["X-Request-ID"] == identifier
                assert request_id.get() is None

            await asyncio.wait_for(
                asyncio.gather(*(read(identifier) for identifier in ids)), timeout=5
            )

    asyncio.run(exercise())
    assert sorted(
        json.loads(line)["request_id"] for line in capsys.readouterr().err.splitlines()
    ) == sorted(ids)


def test_settings_dependency_and_logger_belong_to_app(capsys: pytest.CaptureFixture[str]) -> None:
    settings = [
        Settings(env="test"),
        Settings(
            env="production",
            log_level="ERROR",
            db_host="localhost",
            db_port=5432,
            db_name="test",
            db_user="test",
            db_password=SecretStr("test-only"),
        ),
    ]
    apps = [create_app(config) for config in settings]
    for app in apps:

        @app.get("/env")
        async def env(config: Annotated[Settings, Depends(get_settings)]) -> str:
            return config.env

    for app, config in zip(apps, settings, strict=True):
        assert app.state.settings is config
        with TestClient(app) as client:
            assert client.get("/env").json() == config.env
    (event,) = (
        record
        for record in map(json.loads, capsys.readouterr().err.splitlines())
        if record["event"] == "http.request.completed"
    )
    assert event["environment"] == "test"


def test_partial_stream_error_resets_context_without_a_second_response(
    capsys: pytest.CaptureFixture[str],
) -> None:
    app = create_app(Settings(env="test"))

    @app.get("/partial")
    async def partial() -> StreamingResponse:
        async def chunks() -> AsyncIterator[bytes]:
            yield b"started"
            raise ValueError("private-stream-failure")

        return StreamingResponse(chunks())

    async def exercise() -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            with pytest.raises(RuntimeError, match="HTTP response interrupted"):
                await client.get("/partial")
            assert request_id.get() is None
            # No lifespan on this transport. The existing readiness contract reports 503.
            response = await client.get("/api/v1/ready")
            assert (
                response.status_code == 503 and UUID(response.headers["x-request-id"]).version == 4
            )

    asyncio.run(exercise())
    raw = capsys.readouterr().err
    assert "private-stream" not in raw
    failed, completed = map(json.loads, raw.splitlines())
    assert (failed["event"], failed["status_code"], failed["http_route"]) == (
        "http.request.failed",
        200,
        "/partial",
    )
    assert completed["status_code"] == 503
    assert failed["request_id"] != completed["request_id"]
