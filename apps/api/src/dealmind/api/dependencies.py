from collections.abc import AsyncIterator
from typing import Annotated, cast

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from dealmind.core.config import Settings
from dealmind.db.engine import DatabaseUnavailable
from dealmind.db.session import DatabaseResources, session_scope


def get_settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


def is_application_ready(request: Request) -> bool:
    return bool(request.app.state.is_ready)


def _database(request: Request) -> DatabaseResources | None:
    return cast(DatabaseResources | None, request.app.state.database)


async def is_database_ready(
    request: Request, application_ready: Annotated[bool, Depends(is_application_ready)]
) -> bool:
    database = _database(request)
    return application_ready and database is not None and await database.health.check()


async def get_db_session(request: Request) -> AsyncIterator[AsyncSession]:
    database = _database(request)
    if database is None:
        raise DatabaseUnavailable("Database is not configured")
    async with session_scope(database.sessions) as session:
        yield session
