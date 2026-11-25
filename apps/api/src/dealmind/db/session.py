from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from sqlalchemy import exc
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from dealmind.db.engine import DatabaseUnavailable, is_connectivity_error
from dealmind.db.health import DatabaseHealth


@dataclass(frozen=True)
class DatabaseResources:
    engine: AsyncEngine
    sessions: async_sessionmaker[AsyncSession]
    health: DatabaseHealth


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, autoflush=False, expire_on_commit=False)


@asynccontextmanager
async def session_scope(factory: async_sessionmaker[AsyncSession]) -> AsyncIterator[AsyncSession]:
    try:
        # Closing rolls back any unfinished transaction and releases its connection.
        async with factory() as session:
            yield session
    except exc.TimeoutError as error:
        raise DatabaseUnavailable("Database pool unavailable") from error
    except exc.DBAPIError as error:
        if not is_connectivity_error(error):
            raise
        raise DatabaseUnavailable("Database connection unavailable") from error
