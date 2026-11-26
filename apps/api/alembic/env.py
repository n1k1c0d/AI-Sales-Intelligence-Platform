import asyncio
import sys

from alembic import context
from alembic.util import CommandError
from sqlalchemy import exc
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from dealmind import models  # noqa: F401  (register CRM tables in Base.metadata)
from dealmind.core.config import Settings
from dealmind.db.base import Base
from dealmind.db.engine import DatabaseUnavailable, database_url, is_connectivity_error


def migrate(connection: Connection | None = None) -> None:
    context.configure(
        connection=connection,
        dialect_name="postgresql",
        target_metadata=Base.metadata,
        compare_server_default=True,
        literal_binds=connection is None,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_online() -> None:
    settings = Settings()
    try:
        url = database_url(settings)
    except DatabaseUnavailable:
        raise CommandError("Set APP_DB_PASSWORD before running online migrations") from None
    engine = create_async_engine(
        url,
        poolclass=NullPool,
        hide_parameters=True,
        connect_args={"connect_timeout": settings.db_connect_timeout},
    )
    try:
        async with engine.connect() as connection:
            await connection.run_sync(migrate)
    except exc.DBAPIError as error:
        if not is_connectivity_error(error):
            raise
        raise CommandError("Migration database connection unavailable") from None
    finally:
        await engine.dispose()


if context.is_offline_mode():
    migrate()
else:
    asyncio.run(
        run_online(), loop_factory=asyncio.SelectorEventLoop if sys.platform == "win32" else None
    )
