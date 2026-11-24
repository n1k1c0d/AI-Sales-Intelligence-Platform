from psycopg import OperationalError
from sqlalchemy import URL, exc
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from dealmind.core.config import Settings


class DatabaseUnavailable(Exception):
    """A database connection is not configured or could not be used."""


def database_url(settings: Settings) -> URL:
    if settings.db_password is None:
        raise DatabaseUnavailable("Database password is not configured")
    return URL.create(
        "postgresql+psycopg",
        username=settings.db_user,
        password=settings.db_password.get_secret_value(),
        host=settings.db_host,
        port=settings.db_port,
        database=settings.db_name,
    )


def create_database_engine(settings: Settings) -> AsyncEngine:
    return create_async_engine(
        database_url(settings),
        pool_pre_ping=True,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout,
        connect_args={"connect_timeout": settings.db_connect_timeout},
        echo=False,
        hide_parameters=True,
    )


def is_connectivity_error(error: exc.DBAPIError) -> bool:
    if error.connection_invalidated:
        return True
    state = getattr(error.orig, "sqlstate", None)
    if state is None:
        return isinstance(error.orig, OperationalError)
    return state.startswith(("08", "28")) or state in {"3D000", "53300", "57P01", "57P02", "57P03"}
