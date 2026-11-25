import json
import logging
from datetime import UTC, datetime

from dealmind.core.config import Settings
from dealmind.core.context import request_id


class JsonFormatter(logging.Formatter):
    def __init__(self, environment: str) -> None:
        super().__init__()
        self.environment = environment

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds")
        fields = {
            "timestamp": timestamp.replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": "dealmind-api",
            "environment": self.environment,
            "request_id": request_id.get(),
        }
        for key in (
            "event",
            "http_method",
            "http_route",
            "status_code",
            "duration_ms",
            "exception_type",
        ):
            if key in record.__dict__:
                fields[key] = record.__dict__[key]
        return json.dumps(fields, ensure_ascii=True, separators=(",", ":"))


def create_app_logger(settings: Settings) -> logging.Logger:
    # Each application owns one logger and handler, including in multi-app test processes.
    logger = logging.Logger("dealmind.api", level=settings.log_level)
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter(settings.env))
    logger.addHandler(handler)
    return logger
