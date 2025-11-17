from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from application.dto.models import AccountDTO, CurrencyDTO
from application.interfaces.ports import Clock
from infrastructure.persistence.sqlalchemy.uow import AsyncSqlAlchemyUnitOfWork
from py_accountant.sdk import use_cases
from py_accountant.sdk.errors import UnexpectedError
from py_accountant.sdk.reports.turnover import DailyTurnoverLine, get_account_daily_turnovers

pytestmark = pytest.mark.asyncio


class _Clock(Clock):  # type: ignore[misc]
    def __init__(self, now_dt: datetime):
        self._now = now_dt

    def now(self) -> datetime:  # type: ignore[override]
        return self._now


async def _bootstrap_minimal(uow: AsyncSqlAlchemyUnitOfWork) -> None:
    await uow.currencies.upsert(CurrencyDTO(code="USD", exchange_rate=Decimal("1.0"), is_base=False))
    await uow.currencies.set_base("USD")
    await uow.accounts.create(AccountDTO(id="", name="Cash", full_name="Assets:Cash", currency_code="USD", parent_id=None))
    await uow.accounts.create(AccountDTO(id="", name="Sales", full_name="Income:Sales", currency_code="USD", parent_id=None))


async def test_turnover_empty(async_uow: AsyncSqlAlchemyUnitOfWork) -> None:
    clock = _Clock(datetime.now(UTC))
    await _bootstrap_minimal(async_uow)
    start = clock.now().replace(hour=0, minute=0, second=0, microsecond=0)
    end = start
    rows = await get_account_daily_turnovers(async_uow, clock, start=start, end=end)
    assert rows == []


async def test_turnover_single_day(async_uow: AsyncSqlAlchemyUnitOfWork) -> None:
    now = datetime.now(UTC).replace(hour=10, minute=0, second=0, microsecond=0)
    clock = _Clock(now)
    await _bootstrap_minimal(async_uow)

    # Post two tx on the same day: +100 and -40 -> day debit=100, credit=40
    await use_cases.post_transaction(
        async_uow,
        clock,
        ["DEBIT:Assets:Cash:100:USD", "CREDIT:Income:Sales:100:USD"],
        memo="t1",
    )
    await use_cases.post_transaction(
        async_uow,
        clock,
        ["CREDIT:Assets:Cash:40:USD", "DEBIT:Income:Sales:40:USD"],
        memo="t2",
    )

    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start
    rows = await get_account_daily_turnovers(async_uow, clock, start=start, end=end)
    # Expect two lines (two accounts have turnovers), but we only check Assets:Cash
    ac_lines = [r for r in rows if r.account_full_name == "Assets:Cash"]
    assert len(ac_lines) == 1
    line: DailyTurnoverLine = ac_lines[0]
    assert line.debit_total == Decimal("100")
    assert line.credit_total == Decimal("40")
    assert line.net == Decimal("60")


async def test_turnover_cross_days(async_uow: AsyncSqlAlchemyUnitOfWork) -> None:
    now = datetime(2025, 1, 10, 23, 30, tzinfo=UTC)
    clock = _Clock(now)
    await _bootstrap_minimal(async_uow)

    # Day 1: +100
    await use_cases.post_transaction(
        async_uow,
        clock,
        ["DEBIT:Assets:Cash:100:USD", "CREDIT:Income:Sales:100:USD"],
        memo="d1",
    )
    # Next day 00:05: -20
    clock._now = now + timedelta(minutes=35)
    await use_cases.post_transaction(
        async_uow,
        clock,
        ["CREDIT:Assets:Cash:20:USD", "DEBIT:Income:Sales:20:USD"],
        memo="d2",
    )

    start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    end = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    rows = await get_account_daily_turnovers(async_uow, clock, start=start, end=end, account_full_name="Assets:Cash")
    # Expect two days for Assets:Cash
    assert len(rows) == 2
    assert rows[0].debit_total == Decimal("100") and rows[0].credit_total == Decimal("0")
    assert rows[1].debit_total == Decimal("0") and rows[1].credit_total == Decimal("20")


async def test_turnover_validation(async_uow: AsyncSqlAlchemyUnitOfWork) -> None:
    clock = _Clock(datetime.now(UTC))
    await _bootstrap_minimal(async_uow)
    start = clock.now()
    end = (start - timedelta(days=1))
    with pytest.raises(UnexpectedError):
        await get_account_daily_turnovers(async_uow, clock, start=start, end=end)
