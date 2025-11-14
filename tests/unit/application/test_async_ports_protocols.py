"""Structural tests for async Protocols (ASYNC-05).

These tests ensure that the AsyncSqlAlchemyUnitOfWork and async repository implementations
expose all attributes/methods declared in the new Protocols without performing exhaustive
behavioral checks (covered elsewhere). Failures here typically indicate a breaking interface
change (typo, missing method) that would block ASYNC-06 migration of use cases.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from application.dto.models import AccountDTO, CurrencyDTO, EntryLineDTO, TransactionDTO
from infrastructure.persistence.sqlalchemy.uow import AsyncSqlAlchemyUnitOfWork

pytestmark = pytest.mark.asyncio


async def test_async_uow_structural(async_uow: AsyncSqlAlchemyUnitOfWork):
    """Async UoW exposes required repositories and transaction methods."""
    uow = async_uow
    for attr in ["accounts", "currencies", "transactions", "exchange_rate_events", "commit", "rollback"]:
        assert hasattr(uow, attr), f"Missing attribute/method on Async UoW: {attr}"
    assert hasattr(uow, "session")
    assert uow.session is not None


async def test_async_repositories_structural_and_smoke(async_uow: AsyncSqlAlchemyUnitOfWork):
    """Repositories implement expected async methods and basic smoke operations run."""
    c_repo = async_uow.currencies
    for m in ["get_by_code", "upsert", "list_all", "get_base", "set_base", "clear_base", "bulk_upsert_rates"]:
        assert hasattr(c_repo, m), f"Currency repo missing method {m}"
    await c_repo.upsert(CurrencyDTO(code="USD", exchange_rate=Decimal("1.0")))
    await c_repo.set_base("USD")
    base = await c_repo.get_base()
    assert base and base.code == "USD"

    a_repo = async_uow.accounts
    for m in ["get_by_full_name", "create", "list"]:
        assert hasattr(a_repo, m), f"Account repo missing method {m}"
    acc_dto = AccountDTO(id="", name="Cash", full_name="Assets:Cash", currency_code="USD")
    created = await a_repo.create(acc_dto)
    assert created.full_name == "Assets:Cash"

    t_repo = async_uow.transactions
    for m in ["add", "list_between", "ledger"]:
        assert hasattr(t_repo, m), f"Transaction repo missing method {m}"
    assert not hasattr(t_repo, "account_balance"), "account_balance must be removed from async repo (I13)"
    now = datetime.now(UTC)
    tx = TransactionDTO(
        id="",
        occurred_at=now,
        lines=[
            EntryLineDTO(side="DEBIT", account_full_name="Assets:Cash", amount=Decimal("10"), currency_code="USD"),
            EntryLineDTO(side="CREDIT", account_full_name="Income:Salary", amount=Decimal("10"), currency_code="USD"),
        ],
        memo="Salary",
        meta={"tag": "income"},
    )
    await t_repo.add(tx)
    rows = await t_repo.list_between(now - (now - now), now)
    assert isinstance(rows, list)

    fx_repo = async_uow.exchange_rate_events
    for m in [
        "add_event",
        "list_events",
        "list_old_events",
        "delete_events_by_ids",
        "archive_events",
        "move_events_to_archive",
    ]:
        assert hasattr(fx_repo, m), f"FX events repo missing method {m}"
    await fx_repo.add_event("USD", Decimal("1.0"), now, policy_applied="RAW", source="test")
    evs = await fx_repo.list_events(code="USD")
    assert isinstance(evs, list)


async def test_protocol_absence_typo_guard(async_uow: AsyncSqlAlchemyUnitOfWork):
    """Negative guard: ensure a clearly non-existent attribute is absent (typo detection)."""
    assert not hasattr(async_uow, "not_a_real_repo"), "Unexpected attribute found (typo risk)"


async def test_return_type_expectations(async_uow: AsyncSqlAlchemyUnitOfWork):
    """Simple type expectations for certain methods (list returns list, counts >=0)."""
    fx_repo = async_uow.exchange_rate_events
    now = datetime.now(UTC)
    await fx_repo.add_event("EUR", Decimal("0.9"), now, policy_applied="RAW", source=None)
    rows = await fx_repo.list_events(limit=10)
    assert isinstance(rows, list)
    old_rows = await fx_repo.list_old_events(now, 5)
    assert isinstance(old_rows, list)
    deleted = await fx_repo.delete_events_by_ids([])
    assert isinstance(deleted, int) and deleted >= 0
    archived = await fx_repo.archive_events([], now)
    assert isinstance(archived, int) and archived >= 0


async def test_ledger_empty(async_uow: AsyncSqlAlchemyUnitOfWork):
    """Ledger must return list (possibly empty) rather than None."""
    t_repo = async_uow.transactions
    now = datetime.now(UTC)
    rows = await t_repo.ledger("Assets:Cash", now, now)
    assert isinstance(rows, list)
    assert rows == []
