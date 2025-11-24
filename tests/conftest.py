from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest_asyncio

from py_accountant.infrastructure.persistence.sqlalchemy.models import Base
from py_accountant.infrastructure.persistence.sqlalchemy.uow import AsyncSqlAlchemyUnitOfWork


@pytest_asyncio.fixture
async def async_uow(tmp_path: Path) -> AsyncIterator[AsyncSqlAlchemyUnitOfWork]:
    """Provide an initialized AsyncSqlAlchemyUnitOfWork bound to a file-based SQLite DB.

    Steps:
    1. Instantiate UoW with sqlite+aiosqlite URL inside tmp_path for visible commit/rollback effects.
    2. Create schema via async engine (outside of session transaction for isolation).
    3. Enter UoW transactional context (``__aenter__``) and yield for test usage.
    4. On teardown, exit context ensuring commit/rollback semantics and releasing session.
    """
    db_path = tmp_path / "test_async_fixture.db"
    uow = AsyncSqlAlchemyUnitOfWork(url=f"sqlite+aiosqlite:///{db_path}")
    async with uow.engine.begin() as conn:  # type: ignore[attr-defined]
        await conn.run_sync(Base.metadata.create_all)
    await uow.__aenter__()
    try:
        yield uow
    finally:
        await uow.__aexit__(None, None, None)
