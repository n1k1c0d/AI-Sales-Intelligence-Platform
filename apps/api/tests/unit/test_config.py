import json
from pathlib import Path

import pytest
from pydantic import ValidationError
from pydantic_settings import SettingsError

from dealmind.core.config import Settings


def test_safe_defaults_in_any_working_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".env").write_text("APP_ENV=production", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert Settings().model_dump(mode="json", include={"env", "log_level", "cors_origins"}) == {
        "env": "local",
        "log_level": "INFO",
        "cors_origins": [],
    }


def test_process_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    for key, value in {
        "HOST": "db",
        "PORT": "5432",
        "NAME": "test",
        "USER": "test",
        "PASSWORD": "test-only",
    }.items():
        monkeypatch.setenv("APP_DB_" + key, value)
    monkeypatch.setenv("APP_LOG_LEVEL", "WARNING")
    monkeypatch.setenv("APP_CORS_ORIGINS", '["https://EXAMPLE.org:443","http://[::1]:3000"]')
    settings = Settings()
    assert settings.env == "production" and settings.log_level == "WARNING"
    assert settings.cors_origins == ("https://example.org", "http://[::1]:3000")
    assert Settings(env="test").env == "test"
    with pytest.raises(ValidationError):
        settings.env = "local"


@pytest.mark.parametrize(
    ("name", "value"), [("APP_ENV", "staging"), ("APP_LOG_LEVEL", "TRACE"), ("APP_ENV", "")]
)
def test_invalid_scalar(name: str, value: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(name, value)
    with pytest.raises(ValidationError):
        Settings()


@pytest.mark.parametrize(
    "origin",
    [
        "*",
        "bad",
        "ftp://demo.test",
        "http://",
        "http://demo.test/path",
        "http://demo.test/",
        "https://demo.test?q",
        "https://demo.test#",
        "https://name:private@demo.test",
        "https://*.demo.test",
        "http://host:90000",
    ],
)
def test_invalid_origin(origin: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_CORS_ORIGINS", json.dumps([origin]))
    with pytest.raises(ValidationError) as exc:
        Settings()
    assert "private" not in str(exc.value)


@pytest.mark.parametrize("raw", ["not-json", "{}", '"https://demo.test"', ""])
def test_origins_require_json_array(raw: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_CORS_ORIGINS", raw)
    with pytest.raises((ValidationError, SettingsError)):
        Settings()
