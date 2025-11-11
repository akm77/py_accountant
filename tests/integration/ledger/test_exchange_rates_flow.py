from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from application.dto.models import EntryLineDTO
from application.use_cases_async.accounts import AsyncCreateAccount
from application.use_cases_async.currencies import AsyncCreateCurrency
from application.use_cases_async.ledger import AsyncGetTradingBalance, AsyncPostTransaction
from infrastructure.persistence.inmemory.clock import FixedClock
from infrastructure.persistence.sqlalchemy.uow import AsyncSqlAlchemyUnitOfWork


@pytest.mark.asyncio
async def test_async_update_exchange_rates_flow(tmp_path):
    db_path = tmp_path / "rates.sqlite3"
    url = f"sqlite+aiosqlite:///{db_path}"
    uow = AsyncSqlAlchemyUnitOfWork(url=url)

    from infrastructure.persistence.sqlalchemy.models import Base  # type: ignore
    async with uow.engine.begin() as conn:  # type: ignore[attr-defined]
        await conn.run_sync(Base.metadata.create_all)

    async with uow:
        await AsyncCreateCurrency(uow)("USD", exchange_rate=Decimal("1"))
        await AsyncCreateCurrency(uow)("EUR")
        # Set base USD and upsert EUR rate
        await uow.currencies.set_base("USD")
        cur_eur = await uow.currencies.get_by_code("EUR")
        assert cur_eur is not None
        cur_eur.exchange_rate = Decimal("1.2000000000")
        await uow.currencies.upsert(cur_eur)
        await uow.commit()

    async with uow:
        eur = await uow.currencies.get_by_code("EUR")
        usd = await uow.currencies.get_by_code("USD")
        assert usd and usd.is_base
        assert eur and eur.exchange_rate == Decimal("1.2000000000")


@pytest.mark.asyncio
async def test_async_set_base_currency_single(tmp_path):
    db_path = tmp_path / "base.sqlite3"
    url = f"sqlite+aiosqlite:///{db_path}"
    uow = AsyncSqlAlchemyUnitOfWork(url=url)
    from infrastructure.persistence.sqlalchemy.models import Base  # type: ignore
    async with uow.engine.begin() as conn:  # type: ignore[attr-defined]
        await conn.run_sync(Base.metadata.create_all)

    async with uow:
        await AsyncCreateCurrency(uow)("USD")
        await AsyncCreateCurrency(uow)("JPY")
        await uow.currencies.set_base("USD")
        await uow.currencies.set_base("JPY")
        usd = await uow.currencies.get_by_code("USD")
        jpy = await uow.currencies.get_by_code("JPY")
        assert jpy and jpy.is_base
        assert usd and not usd.is_base


@pytest.mark.asyncio
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
