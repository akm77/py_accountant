from __future__ import annotations

import pytest

from py_accountant.sdk.bootstrap import init_app
from py_accountant.sdk.settings import Settings


@pytest.mark.asyncio
async def test_init_app_in_memory_sqlite_ok():
    ctx = init_app(settings=Settings(async_url="sqlite+aiosqlite:///:memory:"), use_env=False)
    # Create and close UoW to ensure it can be instantiated
    async with ctx.uow_factory() as uow:
        assert uow.session is not None


@pytest.mark.asyncio
async def test_init_app_with_env_ok(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DATABASE_URL_ASYNC", "sqlite+aiosqlite:///:memory:")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    ctx = init_app(use_env=True)
    async with ctx.uow_factory() as uow:
        assert uow.session is not None


def test_invalid_env_raises(monkeypatch: pytest.MonkeyPatch):
    # sync uses async driver -> invalid
    monkeypatch.setenv("DATABASE_URL_ASYNC", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    with pytest.raises(ValueError):
        init_app(use_env=True)

