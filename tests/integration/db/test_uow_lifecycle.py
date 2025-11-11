from __future__ import annotations

from pathlib import Path

import pytest
import pytest_asyncio

from application.dto.models import AccountDTO, CurrencyDTO
from infrastructure.persistence.sqlalchemy.models import Base
from infrastructure.persistence.sqlalchemy.uow import AsyncSqlAlchemyUnitOfWork


@pytest_asyncio.fixture
async def uow_factory(tmp_path: Path):
    async def _make():
        db_path = tmp_path / "uow_lifecycle.db"
        uow = AsyncSqlAlchemyUnitOfWork(url=f"sqlite+aiosqlite:///{db_path}")
        async with uow.engine.begin() as conn:  # type: ignore[attr-defined]
            await conn.run_sync(Base.metadata.create_all)
        return uow
    return _make


@pytest.mark.asyncio
async def test_commit_persists(uow_factory):
    uow = await uow_factory()
    async with uow as tx:
        await tx.currencies.upsert(CurrencyDTO(code="USD", exchange_rate=None, is_base=True))
        await tx.accounts.create(
            AccountDTO(id="", name="Cash", full_name="Assets:Cash", currency_code="USD", parent_id=None)
        )
        await tx.commit()  # explicit commit
    # New UoW reading the same DB should see data
    uow2 = await uow_factory()
    async with uow2 as tx2:
        cur = await tx2.currencies.get_by_code("USD")
        acc = await tx2.accounts.get_by_full_name("Assets:Cash")
        assert cur is not None and cur.code == "USD"
        assert acc is not None and acc.full_name == "Assets:Cash"


@pytest.mark.asyncio
async def test_rollback_discards(uow_factory):
    uow = await uow_factory()
    with pytest.raises(RuntimeError):
        async with uow as tx:
            await tx.currencies.upsert(CurrencyDTO(code="EUR", exchange_rate=None, is_base=True))
            # Force exception to trigger rollback
            raise RuntimeError("boom")
    # Verify not persisted
    uow2 = await uow_factory()
    async with uow2 as tx2:
        cur = await tx2.currencies.get_by_code("EUR")
        assert cur is None


@pytest.mark.asyncio
async def test_double_enter_raises(uow_factory):
    uow = await uow_factory()
    async with uow:
        with pytest.raises(RuntimeError):
            await uow.__aenter__()  # direct re-entry attempt


@pytest.mark.asyncio
async def test_session_property_outside_context_raises(uow_factory):
    uow = await uow_factory()
    with pytest.raises(RuntimeError):
        _ = uow.session  # accessing before context
    async with uow:
        _ = uow.session  # inside OK
    with pytest.raises(RuntimeError):
        _ = uow.session  # after exit


@pytest.mark.asyncio
async def test_repositories_lazy_singleton_per_context(uow_factory):
    uow = await uow_factory()
    async with uow as tx:
        a1 = tx.accounts
        a2 = tx.accounts
        c1 = tx.currencies
        c2 = tx.currencies
        assert a1 is a2
        assert c1 is c2
    # After exit new context gets new repo objects
    async with uow as tx2:
        assert tx2.accounts is not a1
        assert tx2.currencies is not c1


@pytest.mark.asyncio
async def test_no_retry_backoff_left_in_source():
    from pathlib import Path as _P
    src = _P(__file__).parents[3] / "src" / "infrastructure" / "persistence" / "sqlalchemy" / "uow.py"
    text = src.read_text(encoding="utf-8")
    forbidden = ["retry", "backoff", "statement_timeout", "_commit_with_retry", "_is_transient_error"]
    for token in forbidden:
        assert token not in text, f"forbidden token still present: {token}"
