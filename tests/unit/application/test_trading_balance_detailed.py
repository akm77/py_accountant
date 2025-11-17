from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from application.dto.models import EntryLineDTO
from application.use_cases.ledger import (
    CreateAccount,
    CreateCurrency,
    GetTradingBalanceDetailedDTOs,
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
        GetTradingBalanceDetailedDTOs(uow, clock)("")


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
    # 100 EUR sale (rate 1.2 -> ~83.33 base)
    post([
        EntryLineDTO(side="DEBIT", account_full_name="Assets:BankEUR", amount=Decimal("100"), currency_code="EUR", exchange_rate=Decimal("1.2")),
        EntryLineDTO(side="CREDIT", account_full_name="Income:Sales", amount=Decimal("100"), currency_code="EUR", exchange_rate=Decimal("1.2")),
    ])
    lines = GetTradingBalanceDetailedDTOs(uow, clock)("USD")
    # Fields present
    for line in lines:
        assert line.debit_base is not None
        assert line.credit_base is not None
        assert line.net_base is not None
        assert line.used_rate is not None
    # EUR line conversion check
    eur_line = next(line for line in lines if line.currency_code == "EUR")
    assert eur_line.used_rate == Decimal("1.2")


def test_get_trading_balance_detailed_fallback_rate():
    uow = setup_uow()
    CreateCurrency(uow)("USD", exchange_rate=Decimal("1"))
    # Domain requires rate_to_base for non-base currencies; emulate fallback with rate=1
    CreateCurrency(uow)("JPY", exchange_rate=Decimal("1"))
    CreateAccount(uow)("Assets:Cash", "USD")
    CreateAccount(uow)("Assets:BankJPY", "JPY")
    CreateAccount(uow)("Income:Sales", "USD")
    clock = FixedClock(fixed=datetime.now(UTC))
    post = PostTransaction(uow, clock)
    post([
        EntryLineDTO(side="DEBIT", account_full_name="Assets:BankJPY", amount=Decimal("1000"), currency_code="JPY"),
        EntryLineDTO(side="CREDIT", account_full_name="Income:Sales", amount=Decimal("1000"), currency_code="JPY"),
    ])
    lines = GetTradingBalanceDetailedDTOs(uow, clock)("USD")
    jpy_line = next(line for line in lines if line.currency_code == "JPY")
    # With rate 1.0, converted numbers equal raw numbers
    assert jpy_line.used_rate == Decimal("1")
    assert jpy_line.debit_base == jpy_line.debit
    assert jpy_line.credit_base == jpy_line.credit
    assert jpy_line.net_base == jpy_line.net
