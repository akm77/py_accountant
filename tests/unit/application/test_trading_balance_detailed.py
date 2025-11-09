from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from application.dto.models import EntryLineDTO
from application.use_cases.ledger import (
    CreateAccount,
    CreateCurrency,
    GetTradingBalanceDetailed,
    PostTransaction,
)
from domain import DomainError
from infrastructure.persistence.inmemory.clock import FixedClock
from infrastructure.persistence.inmemory.uow import InMemoryUnitOfWork


def setup_uow() -> InMemoryUnitOfWork:
    return InMemoryUnitOfWork()


def test_get_trading_balance_detailed_requires_base_currency():
    uow = setup_uow()
    clock = FixedClock(fixed=datetime.now(UTC))
    with pytest.raises(DomainError):
        GetTradingBalanceDetailed(uow, clock)(None)


def test_get_trading_balance_detailed_basic_conversion():
    uow = setup_uow()
    CreateCurrency(uow)("USD", exchange_rate=Decimal("1"))
    CreateCurrency(uow)("EUR", exchange_rate=Decimal("1.2"))
    CreateAccount(uow)("Assets:Cash", "USD")
    CreateAccount(uow)("Assets:BankEUR", "EUR")
    CreateAccount(uow)("Income:Sales", "USD")
    clock = FixedClock(fixed=datetime.now(UTC))
    post = PostTransaction(uow, clock)
    # 120 USD sale
    post([
        EntryLineDTO(side="DEBIT", account_full_name="Assets:Cash", amount=Decimal("120"), currency_code="USD"),
        EntryLineDTO(side="CREDIT", account_full_name="Income:Sales", amount=Decimal("120"), currency_code="USD"),
    ])
    # 100 EUR sale (rate 1.2 -> 83.333.. base)
    post([
        EntryLineDTO(side="DEBIT", account_full_name="Assets:BankEUR", amount=Decimal("100"), currency_code="EUR", exchange_rate=Decimal("1.2")),
        EntryLineDTO(side="CREDIT", account_full_name="Income:Sales", amount=Decimal("100"), currency_code="EUR", exchange_rate=Decimal("1.2")),
    ])
    tb = GetTradingBalanceDetailed(uow, clock)("USD")
    # All converted_* present
    for line in tb.lines:
        assert line.converted_debit is not None
        assert line.converted_credit is not None
        assert line.converted_balance is not None
        assert line.rate_used is not None
    # EUR line conversion check (100/1.2 = 83.333...)
    eur = next(l for l in tb.lines if l.currency_code == "EUR")
    assert eur.rate_used == Decimal("1.2") and eur.rate_fallback is False
    # base_total equals sum of converted balances
    base_total = sum(l.converted_balance for l in tb.lines)  # type: ignore[arg-type]
    assert tb.base_total == base_total


def test_get_trading_balance_detailed_fallback_rate():
    uow = setup_uow()
    CreateCurrency(uow)("USD", exchange_rate=Decimal("1"))
    CreateCurrency(uow)("JPY")  # no rate
    CreateAccount(uow)("Assets:Cash", "USD")
    CreateAccount(uow)("Assets:BankJPY", "JPY")
    CreateAccount(uow)("Income:Sales", "USD")
    clock = FixedClock(fixed=datetime.now(UTC))
    post = PostTransaction(uow, clock)
    post([
        EntryLineDTO(side="DEBIT", account_full_name="Assets:BankJPY", amount=Decimal("1000"), currency_code="JPY"),
        EntryLineDTO(side="CREDIT", account_full_name="Income:Sales", amount=Decimal("1000"), currency_code="JPY"),
    ])
    tb = GetTradingBalanceDetailed(uow, clock)("USD")
    jpy = next(l for l in tb.lines if l.currency_code == "JPY")
    assert jpy.rate_used == Decimal("1") and jpy.rate_fallback is True
    assert jpy.converted_debit == jpy.total_debit
    assert jpy.converted_credit == jpy.total_credit
    assert jpy.converted_balance == jpy.balance

