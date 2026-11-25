import pytest
from pydantic import SecretStr, ValidationError

from dealmind.core.config import Settings
from dealmind.db.engine import DatabaseUnavailable, database_url


def test_defaults_and_missing_password() -> None:
    config = Settings()
    assert (config.db_host, config.db_port, config.db_name, config.db_user) == (
        "127.0.0.1",
        5433,
        "dealmind",
        "dealmind",
    )
    assert (
        config.db_pool_size,
        config.db_max_overflow,
        config.db_pool_timeout,
        config.db_connect_timeout,
        config.db_health_timeout,
    ) == (5, 5, 5, 3, 5)
    with pytest.raises(DatabaseUnavailable):
        database_url(config)
    with pytest.raises(ValidationError):
        Settings(env="production")
    with pytest.raises(ValidationError):
        Settings(env="production", db_password=SecretStr("example-only"))


def test_env_and_special_password(monkeypatch: pytest.MonkeyPatch) -> None:
    password = "test@%:/only"
    for key, value in {
        "HOST": "db",
        "PORT": "5432",
        "NAME": "dm",
        "USER": "tester",
        "PASSWORD": password,
        "POOL_SIZE": "2",
        "MAX_OVERFLOW": "0",
        "POOL_TIMEOUT": "2",
        "CONNECT_TIMEOUT": "4",
        "HEALTH_TIMEOUT": "1.5",
    }.items():
        monkeypatch.setenv("APP_DB_" + key, value)
    config = Settings(env="production")
    url = database_url(config)
    assert (url.drivername, url.host, url.port, url.database, url.username, url.password) == (
        "postgresql+psycopg",
        "db",
        5432,
        "dm",
        "tester",
        password,
    )
    assert (
        config.db_pool_size,
        config.db_max_overflow,
        config.db_pool_timeout,
        config.db_connect_timeout,
        config.db_health_timeout,
    ) == (2, 0, 2, 4, 1.5)
    assert all(
        password not in diagnostic
        for diagnostic in (repr(config), str(config), repr(url), str(url), config.model_dump_json())
    )


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("HOST", " "),
        ("USER", ""),
        ("NAME", " "),
        ("PORT", "0"),
        ("PORT", "65536"),
        ("POOL_SIZE", "0"),
        ("MAX_OVERFLOW", "-1"),
        ("POOL_TIMEOUT", "0"),
        ("CONNECT_TIMEOUT", "0"),
        ("HEALTH_TIMEOUT", "nan"),
        ("PASSWORD", ""),
    ],
)
def test_invalid_database_settings(key: str, value: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_DB_" + key, value)
    with pytest.raises(ValidationError):
        Settings()


def test_import_opens_no_connections(monkeypatch: pytest.MonkeyPatch) -> None:
    # Import in a fresh interpreter, blocking network activity before application import.
    import subprocess
    import sys

    monkeypatch.setenv("APP_DB_PASSWORD", "test-only")
    program = """import sys
def deny(event,args):
    if event in ('socket.connect', 'socket.getaddrinfo'):
        raise AssertionError(event)
sys.addaudithook(deny)
import dealmind.main, dealmind.db.engine, dealmind.db.session
assert dealmind.main.app.state.database is None
"""
    subprocess.run([sys.executable, "-c", program], check=True)
