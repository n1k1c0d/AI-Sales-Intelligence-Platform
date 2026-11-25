import json
import logging
from datetime import datetime, timedelta

import pytest

from dealmind.core.config import Settings
from dealmind.core.logging import JsonFormatter, create_app_logger


def test_json_record_has_utc_time_and_explicit_fields() -> None:
    record = logging.LogRecord(
        "dealmind.api", logging.INFO, __file__, 1, "hello %s", ("world",), None
    )
    record.created = 0.125
    data = json.loads(JsonFormatter("test").format(record))
    assert data == {
        "timestamp": "1970-01-01T00:00:00.125Z",
        "level": "INFO",
        "logger": "dealmind.api",
        "service": "dealmind-api",
        "environment": "test",
        "message": "hello world",
        "request_id": None,
    }
    assert datetime.fromisoformat(data["timestamp"]).utcoffset() == timedelta(0)


def test_loggers_have_independent_levels_and_no_duplicate_handlers(
    capsys: pytest.CaptureFixture[str],
) -> None:
    foreign = logging.getLogger("dealmind")
    handlers = list(foreign.handlers)
    info = create_app_logger(Settings(env="local", log_level="INFO"))
    debug = create_app_logger(Settings(env="test", log_level="DEBUG"))
    info.debug("filtered")
    debug.debug("visible")
    info.error("safe message", extra={"password": "private-probe"})
    raw = capsys.readouterr().err
    assert "private-probe" not in raw
    assert [(d["environment"], d["message"]) for d in map(json.loads, raw.splitlines())] == [
        ("test", "visible"),
        ("local", "safe message"),
    ]
    assert len(info.handlers) == len(debug.handlers) == 1
    assert foreign.handlers == handlers
