from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from application.dto.models import AccountDTO, CurrencyDTO
from application.interfaces.ports import Clock
from infrastructure.persistence.sqlalchemy.uow import AsyncSqlAlchemyUnitOfWork
from py_accountant.sdk import use_cases

pytestmark = pytest.mark.asyncio


class _Clock(Clock):  # type: ignore[misc]
    def __init__(self, now_dt: datetime):
        self._now = now_dt

    def now(self) -> datetime:  # type: ignore[override]
        return self._now


async def _bootstrap_minimal(uow: AsyncSqlAlchemyUnitOfWork) -> None:
    # currencies
    await uow.currencies.upsert(CurrencyDTO(code="USD", exchange_rate=Decimal("1.0"), is_base=False))
    await uow.currencies.set_base("USD")
    # accounts
    await uow.accounts.create(
        AccountDTO(id="", name="Cash", full_name="Assets:Cash", currency_code="USD", parent_id=None)
    )
    await uow.accounts.create(
        AccountDTO(id="", name="Sales", full_name="Income:Sales", currency_code="USD", parent_id=None)
    )


async def test_sdk_balance_fast_path_simple(async_uow: AsyncSqlAlchemyUnitOfWork) -> None:
    now = datetime.now(UTC)
    clock = _Clock(now)
    await _bootstrap_minimal(async_uow)

    # Post one transaction: +100 to Assets:Cash
    await use_cases.post_transaction(
        async_uow,
        clock,
        [
            "DEBIT:Assets:Cash:100:USD",
            "CREDIT:Income:Sales:100:USD",
        ],
        memo="sale-1",
        meta={"idempotency_key": "sdk-fastpath-1"},
    )

    # Current balance should be 100 via fast-path (account_balances)
    bal = await use_cases.get_account_balance(async_uow, clock, "Assets:Cash")
    assert bal == Decimal("100")


async def test_sdk_balance_fast_path_accumulates(async_uow: AsyncSqlAlchemyUnitOfWork) -> None:
    now = datetime.now(UTC)
    clock = _Clock(now)
    await _bootstrap_minimal(async_uow)

    # +100, then -40 => net 60
    await use_cases.post_transaction(
        async_uow,
        clock,
        [
            "DEBIT:Assets:Cash:100:USD",
            "CREDIT:Income:Sales:100:USD",
        ],
        memo="t1",
    )
    clock._now = now + timedelta(seconds=1)
    await use_cases.post_transaction(
        async_uow,
        clock,
        [
            "CREDIT:Assets:Cash:40:USD",
            "DEBIT:Income:Sales:40:USD",
        ],
        memo="t2",
    )
    bal = await use_cases.get_account_balance(async_uow, clock, "Assets:Cash")
    assert bal == Decimal("60")


async def test_sdk_balance_empty_zero(async_uow: AsyncSqlAlchemyUnitOfWork) -> None:
    clock = _Clock(datetime.now(UTC))
    await _bootstrap_minimal(async_uow)
    bal = await use_cases.get_account_balance(async_uow, clock, "Assets:Cash")
    assert bal == Decimal("0")

