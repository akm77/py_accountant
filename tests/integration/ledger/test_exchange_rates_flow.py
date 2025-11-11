from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest


@pytest.mark.xfail(reason="REWRITE-DOMAIN (I13): repository no longer aggregates trading balance", strict=False)
async def test_async_rounding_applied_in_trading_balance(tmp_path):
    db_path = tmp_path / "trading.sqlite3"
    url = f"sqlite+aiosqlite:///{db_path}"
    uow = AsyncSqlAlchemyUnitOfWork(url=url)
    from infrastructure.persistence.sqlalchemy.models import Base  # type: ignore
    async with uow.engine.begin() as conn:  # type: ignore[attr-defined]
        await conn.run_sync(Base.metadata.create_all)

    async with uow:
        await AsyncCreateCurrency(uow)("USD", exchange_rate=Decimal("1"))
        await AsyncCreateCurrency(uow)("JPY")
        await uow.currencies.set_base("USD")
        jpy = await uow.currencies.get_by_code("JPY")
        assert jpy is not None
        jpy.exchange_rate = Decimal("150.1234567890")
        await uow.currencies.upsert(jpy)
        await AsyncCreateAccount(uow)("Assets:CashUSD", "USD")
        await AsyncCreateAccount(uow)("Assets:CashJPY", "JPY")
        clock = FixedClock(datetime.now(UTC))
        post = AsyncPostTransaction(uow, clock)
        await post([
            EntryLineDTO(side="DEBIT", account_full_name="Assets:CashUSD", amount=Decimal("100"), currency_code="USD"),
            EntryLineDTO(side="CREDIT", account_full_name="Assets:CashJPY", amount=Decimal("15012.34567890"), currency_code="JPY", exchange_rate=Decimal("150.1234567890")),
        ])
        await uow.commit()

    async with uow:
        clock2 = FixedClock(datetime.now(UTC))
        tb = await AsyncGetTradingBalance(uow, clock2)(base_currency=None)
        assert tb.base_currency == "USD"
        assert all(len(str(line.converted_balance).split('.')[-1]) <= 2 for line in tb.lines if line.converted_balance is not None)
