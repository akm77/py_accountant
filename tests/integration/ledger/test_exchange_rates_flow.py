from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from application.dto.models import EntryLineDTO, RateUpdateInput
from application.use_cases.exchange_rates import UpdateExchangeRates
from application.use_cases.ledger import (
    CreateAccount,
    CreateCurrency,
    GetTradingBalance,
    PostTransaction,
)
from domain import ExchangeRatePolicy
from infrastructure.persistence.inmemory.clock import FixedClock
from infrastructure.persistence.sqlalchemy.uow import SqlAlchemyUnitOfWork


def test_sql_update_exchange_rates_flow():
    uow = SqlAlchemyUnitOfWork(url="sqlite+pysqlite:///:memory:")
    CreateCurrency(uow)("USD", exchange_rate=Decimal("1"))
    CreateCurrency(uow)("EUR")
    UpdateExchangeRates(uow, policy=ExchangeRatePolicy(mode="last_write"))(
        [RateUpdateInput(code="EUR", rate=Decimal("1.2000000000"))], set_base="USD"
    )
    eur = uow.currencies.get_by_code("EUR")
    usd = uow.currencies.get_by_code("USD")
    assert usd and usd.is_base
    assert eur and eur.exchange_rate == Decimal("1.2000000000")


def test_sql_set_base_currency_single():
    uow = SqlAlchemyUnitOfWork(url="sqlite+pysqlite:///:memory:")
    CreateCurrency(uow)("USD")
    CreateCurrency(uow)("JPY")
    uow.currencies.set_base("USD")
    uow.currencies.set_base("JPY")
    usd = uow.currencies.get_by_code("USD")
    jpy = uow.currencies.get_by_code("JPY")
    assert jpy and jpy.is_base
    assert usd and not usd.is_base


def test_sql_rounding_applied_in_trading_balance():
    uow = SqlAlchemyUnitOfWork(url="sqlite+pysqlite:///:memory:")
    CreateCurrency(uow)("USD", exchange_rate=Decimal("1"))
    CreateCurrency(uow)("JPY")
    UpdateExchangeRates(uow)([RateUpdateInput(code="JPY", rate=Decimal("150.1234567890"))], set_base="USD")
    CreateAccount(uow)("Assets:CashUSD", "USD")
    CreateAccount(uow)("Assets:CashJPY", "JPY")
    clock = FixedClock(datetime.now(UTC))
    post = PostTransaction(uow, clock)
    # Balance in base: credit JPY amount = 100 USD * rate
    post([
        EntryLineDTO(side="DEBIT", account_full_name="Assets:CashUSD", amount=Decimal("100"), currency_code="USD"),
        EntryLineDTO(side="CREDIT", account_full_name="Assets:CashJPY", amount=Decimal("15012.34567890"), currency_code="JPY", exchange_rate=Decimal("150.1234567890")),
    ])
    gb = GetTradingBalance(uow, clock)()
    assert gb.base_currency == "USD"
    # Converted balances must be quantized (money scale=2)
    assert all(len(str(l.converted_balance).split('.')[-1]) <= 2 for l in gb.lines if l.converted_balance is not None)
