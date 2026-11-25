import asyncio
import logging
from time import monotonic

from sqlalchemy import exc, text
from sqlalchemy.ext.asyncio import AsyncEngine

from dealmind.db.engine import is_connectivity_error


class DatabaseHealth:
    def __init__(self, engine: AsyncEngine, timeout: float, logger: logging.Logger) -> None:
        self.engine = engine
        self.timeout = timeout
        self.logger = logger
        self._next_warning = 0.0

    async def check(self) -> bool:
        started = monotonic()
        try:
            async with asyncio.timeout(self.timeout), self.engine.connect() as connection:
                result = await connection.execute(text("SELECT 1"))
                value: object = result.scalar_one()
                ready = value == 1
        except (TimeoutError, exc.TimeoutError, exc.DBAPIError) as error:
            if isinstance(error, exc.DBAPIError) and not is_connectivity_error(error):
                raise
            now = monotonic()
            if now >= self._next_warning:
                self._next_warning = now + 30
                self.logger.warning(
                    "Database readiness check failed",
                    extra={
                        "event": "database.healthcheck.failed",
                        "exception_type": type(error).__name__,
                        "duration_ms": round((now - started) * 1000, 3),
                    },
                )
            return False
        if ready:
            self._next_warning = 0.0
        return ready
