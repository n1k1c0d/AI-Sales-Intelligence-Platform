import os

import pytest


def pytest_configure(config: pytest.Config) -> None:
    # The ASGI entry point constructs its default app during test module collection.
    monkeypatch = pytest.MonkeyPatch()
    config.add_cleanup(monkeypatch.undo)
    for name in tuple(os.environ):
        if not (
            name.startswith("APP_DB_") or name in {"APP_ENV", "APP_LOG_LEVEL", "APP_CORS_ORIGINS"}
        ):
            continue
        monkeypatch.delenv(name, raising=False)
