from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from sqlalchemy import text

from infrastructure.persistence.sqlalchemy.uow import (
    AsyncSqlAlchemyUnitOfWork,
    SyncUnitOfWorkWrapper,
)


@pytest.mark.asyncio
async def test_async_uow_commit(tmp_path: Path) -> None:
    """Async UoW commits on successful context exit.

    Create a table once, insert a row inside the UoW, and verify the row is visible after exit.
    """
    db_path = tmp_path / "commit.sqlite3"
    url = f"sqlite+aiosqlite:///{db_path}"

    uow = AsyncSqlAlchemyUnitOfWork(url)

    # Prepare schema outside of transactional test to avoid DDL rollback semantics
    async with uow.session_factory() as s:  # type: ignore[attr-defined]
        await s.execute(text("CREATE TABLE IF NOT EXISTS t (id INTEGER PRIMARY KEY, v TEXT)"))
        await s.commit()

    async with uow as _:
        await uow.session.execute(text("INSERT INTO t (v) VALUES ('x')"))
        # Implicit commit on exit

    # Verify visibility from a fresh session
    async with uow.session_factory() as s:  # type: ignore[attr-defined]
        res = await s.execute(text("SELECT COUNT(*) FROM t"))
        count = res.scalar_one()
        assert count == 1


@pytest.mark.asyncio
async def test_async_uow_rollback(tmp_path: Path) -> None:
    """Async UoW rolls back on exception inside the context manager."""
    db_path = tmp_path / "rollback.sqlite3"
    url = f"sqlite+aiosqlite:///{db_path}"

    uow = AsyncSqlAlchemyUnitOfWork(url)

    # Prepare schema
    async with uow.session_factory() as s:  # type: ignore[attr-defined]
        await s.execute(text("CREATE TABLE IF NOT EXISTS t (id INTEGER PRIMARY KEY, v TEXT)"))
        await s.commit()

    class Boom(Exception):
        pass

    with pytest.raises(Boom):
        async with uow as _:
            await uow.session.execute(text("INSERT INTO t (v) VALUES ('x')"))
            raise Boom("trigger rollback")

    # Verify no rows after rollback
    async with uow.session_factory() as s:  # type: ignore[attr-defined]
        res = await s.execute(text("SELECT COUNT(*) FROM t"))
        count = res.scalar_one()
        assert count == 0


def test_sync_wrapper_basic(tmp_path: Path) -> None:
    """Sync wrapper should be able to enter/exit and call commit/rollback."""
    db_path = tmp_path / "wrapper.sqlite3"
    url = f"sqlite+aiosqlite:///{db_path}"

    wrapper = SyncUnitOfWorkWrapper(AsyncSqlAlchemyUnitOfWork(url))
    with wrapper:
        wrapper.commit()
        wrapper.rollback()

    # Ensure wrapper refuses to run inside an active loop
    async def _inside_loop() -> None:
        w2 = SyncUnitOfWorkWrapper(AsyncSqlAlchemyUnitOfWork(url))
        with pytest.raises(RuntimeError):
            w2.commit()

    # Run the above inside a loop to validate guard
    asyncio.run(_inside_loop())

