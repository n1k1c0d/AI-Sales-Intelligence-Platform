from uuid import uuid4

import pytest
from sqlalchemy import exc, text
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.pool import QueuePool

from dealmind.db.session import create_session_factory, session_scope

pytestmark = [pytest.mark.database, pytest.mark.asyncio]


async def test_transaction_visibility_and_cleanup(engine: AsyncEngine) -> None:
    table = "dm007_" + uuid4().hex  # Local identifier, never HTTP or external input.
    factory = create_session_factory(engine)
    async with engine.begin() as connection:
        assert (await connection.execute(text("SELECT 1"))).scalar_one() == 1
        await connection.execute(text(f"CREATE TABLE {table} (id integer PRIMARY KEY)"))
    insert = text(f"INSERT INTO {table} (id) VALUES (:id)")
    try:
        async with session_scope(factory) as writer, session_scope(factory) as reader:
            assert writer is not reader
            await writer.execute(insert, {"id": 1})
            assert (await reader.execute(text(f"SELECT count(*) FROM {table}"))).scalar_one() == 0
            await writer.commit()
            assert (await reader.execute(text(f"SELECT id FROM {table}"))).scalar_one() == 1
            await writer.execute(insert, {"id": 2})
            await writer.rollback()
        with pytest.raises(ValueError, match="cancel operation"):
            async with session_scope(factory) as session, session.begin():
                await session.execute(insert, {"id": 3})
                raise ValueError("cancel operation")
        async with session_scope(factory) as unfinished:
            await unfinished.execute(insert, {"id": 4})  # Dependency exit must never commit.
        with pytest.raises(exc.IntegrityError):
            async with session_scope(factory) as invalid:
                await invalid.execute(insert, {"id": 1})
        async with session_scope(factory) as auditor:
            assert (await auditor.execute(text(f"SELECT id FROM {table}"))).scalars().all() == [1]
        assert isinstance(engine.pool, QueuePool)
        assert engine.pool.checkedout() == 0
    finally:
        async with engine.begin() as connection:
            await connection.execute(text(f"DROP TABLE {table}"))
