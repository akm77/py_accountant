# isort: skip_file
from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy.exc import DBAPIError

from infrastructure.config.settings import get_settings
from infrastructure.persistence.sqlalchemy.uow import AsyncSqlAlchemyUnitOfWork


# Keep pytestmark immediately after imports for clarity
pytestmark = pytest.mark.asyncio


class _DummyOrig(Exception):
    sqlstate = "40001"  # serialization failure


@pytest.mark.xfail(reason="OBSOLETE (I14): retry logic removed from AsyncUoW")
async def test_commit_retries_then_succeeds(monkeypatch: Any) -> None:
    """Commit should retry on transient DBAPIError and eventually succeed."""
    # Ensure fresh settings and configure small backoffs for fast test
    get_settings.cache_clear()  # type: ignore[attr-defined]
    monkeypatch.setenv("DB_RETRY_ATTEMPTS", "3")
    monkeypatch.setenv("DB_RETRY_BACKOFF_MS", "1")
    monkeypatch.setenv("DB_RETRY_MAX_BACKOFF_MS", "2")

    uow = AsyncSqlAlchemyUnitOfWork("sqlite+aiosqlite:///:memory:")

    calls: dict[str, int] = {"commit": 0, "rollback": 0}

    async def _fake_commit():
        calls["commit"] += 1
        # Fail twice, then succeed
        if calls["commit"] < 3:
            raise DBAPIError("COMMIT", {}, _DummyOrig(), connection_invalidated=False)
        return None

    async def _fake_rollback():
        calls["rollback"] += 1
        return None

    async with uow:
        # Patch underlying AsyncSession methods
        assert uow.session is not None
        monkeypatch.setattr(uow.session, "commit", _fake_commit)
        monkeypatch.setattr(uow.session, "rollback", _fake_rollback)
        await uow.commit()

    # Expect two rollbacks (after two transient failures) and three commit calls
    assert calls["commit"] == 3
    assert calls["rollback"] == 2


@pytest.mark.xfail(reason="OBSOLETE (I14): retry logic removed from AsyncUoW")
async def test_commit_gives_up_on_non_transient(monkeypatch: Any) -> None:
    """Commit should not retry on non-transient errors and raise immediately."""
    get_settings.cache_clear()  # type: ignore[attr-defined]
    monkeypatch.setenv("DB_RETRY_ATTEMPTS", "3")
    uow = AsyncSqlAlchemyUnitOfWork("sqlite+aiosqlite:///:memory:")

    class _NonTransient(Exception):
        pass

    async def _fake_commit():
        raise _NonTransient("boom")

    async with uow:
        monkeypatch.setattr(uow.session, "commit", _fake_commit)  # type: ignore[arg-type]
        with pytest.raises(_NonTransient):
            await uow.commit()
