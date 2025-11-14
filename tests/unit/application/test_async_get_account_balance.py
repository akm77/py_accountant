from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from application.dto.models import EntryLineDTO
from application.interfaces.ports import Clock
from application.use_cases_async.ledger import AsyncGetAccountBalance, AsyncPostTransaction
from infrastructure.persistence.sqlalchemy.uow import AsyncSqlAlchemyUnitOfWork

pytestmark = pytest.mark.asyncio


class _Clock(Clock):  # type: ignore[misc]
    def __init__(self, now_dt: datetime):
        self._now = now_dt

    def now(self) -> datetime:  # type: ignore[override]
        return self._now


async def _bootstrap_minimal(uow: AsyncSqlAlchemyUnitOfWork) -> None:
    # currencies
    await uow.currencies.upsert(type("Cur", (), {"code": "USD", "exchange_rate": Decimal("1.0"), "is_base": False})())  # type: ignore[arg-type]
    await uow.currencies.set_base("USD")
    # accounts
    await uow.accounts.create(type("Acc", (), {"id": "", "name": "Cash", "full_name": "Assets:Cash", "currency_code": "USD", "parent_id": None})())  # type: ignore[arg-type]
    await uow.accounts.create(type("Acc", (), {"id": "", "name": "Salary", "full_name": "Income:Salary", "currency_code": "USD", "parent_id": None})())  # type: ignore[arg-type]


async def test_balance_computed_via_ledger_scan(async_uow: AsyncSqlAlchemyUnitOfWork):
    start = datetime.now(UTC)
    clock = _Clock(start)
    await _bootstrap_minimal(async_uow)

    post = AsyncPostTransaction(async_uow, clock)
    # Post two transactions: +100, -40 => net 60
    await post([
        EntryLineDTO(side="DEBIT", account_full_name="Assets:Cash", amount=Decimal("100"), currency_code="USD"),
        EntryLineDTO(side="CREDIT", account_full_name="Income:Salary", amount=Decimal("100"), currency_code="USD"),
    ], memo="first")
    clock._now = start + timedelta(seconds=1)
    await post([
        EntryLineDTO(side="CREDIT", account_full_name="Assets:Cash", amount=Decimal("40"), currency_code="USD"),
        EntryLineDTO(side="DEBIT", account_full_name="Income:Salary", amount=Decimal("40"), currency_code="USD"),
    ], memo="second")

    get_bal = AsyncGetAccountBalance(async_uow, clock)
    bal = await get_bal("Assets:Cash")
    assert bal == Decimal("60"), bal


async def test_balance_empty_zero(async_uow: AsyncSqlAlchemyUnitOfWork):
    clock = _Clock(datetime.now(UTC))
    await _bootstrap_minimal(async_uow)
    bal = await AsyncGetAccountBalance(async_uow, clock)("Assets:Cash")
    assert bal == Decimal("0")

