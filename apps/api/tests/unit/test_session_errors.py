from unittest.mock import MagicMock

import pytest
from sqlalchemy import exc
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from dealmind.db.engine import DatabaseUnavailable
from dealmind.db.session import session_scope


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error",
    [
        exc.TimeoutError("pool timeout"),
        exc.OperationalError(None, None, OSError(), connection_invalidated=True),
    ],
)
async def test_session_translates_connectivity_failure_after_cleanup(error: Exception) -> None:
    factory = MagicMock(spec=async_sessionmaker[AsyncSession])
    with pytest.raises(DatabaseUnavailable) as caught:
        async with session_scope(factory):
            raise error
    assert caught.value.__cause__ is error
    factory.return_value.__aexit__.assert_awaited_once()
