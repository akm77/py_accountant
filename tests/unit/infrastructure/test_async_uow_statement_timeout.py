from __future__ import annotations

from typing import Any

import pytest

from py_accountant.infrastructure.config.settings import get_settings
from py_accountant.infrastructure.persistence.sqlalchemy.uow import AsyncSqlAlchemyUnitOfWork

pytestmark = pytest.mark.asyncio


async def test_set_local_statement_timeout_applied_on_postgres(monkeypatch: Any) -> None:
    """Weak smoke test: ensure entering UoW with Postgres dialect and timeout set does not raise.

    Detailed verification of SET LOCAL executed is deferred to integration tests (requires real Postgres).
    """
    get_settings.cache_clear()  # type: ignore[attr-defined]
    monkeypatch.setenv("DB_STATEMENT_TIMEOUT_MS", "1234")

    uow = AsyncSqlAlchemyUnitOfWork("sqlite+aiosqlite:///:memory:")

    class _FakeDialect:
        name = "postgresql"

    monkeypatch.setattr(uow.engine, "dialect", _FakeDialect())  # type: ignore[arg-type]

    async with uow:
        # No exception should occur
        pass


async def test_noop_on_sqlite(monkeypatch: Any) -> None:
    """Ensure no errors are raised when dialect is sqlite and timeout is set."""
    get_settings.cache_clear()  # type: ignore[attr-defined]
    monkeypatch.setenv("DB_STATEMENT_TIMEOUT_MS", "999")
    uow = AsyncSqlAlchemyUnitOfWork("sqlite+aiosqlite:///:memory:")

    class _FakeDialect:
        name = "sqlite"

    monkeypatch.setattr(uow.engine, "dialect", _FakeDialect())  # type: ignore[arg-type]
    async with uow:
        pass
