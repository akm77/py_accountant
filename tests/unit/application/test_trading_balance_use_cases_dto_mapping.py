from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from py_accountant.application.dto.models import (
    EntryLineDTO,
    TradingBalanceLineDetailed,
    TradingBalanceLineSimple,
)
from py_accountant.application.use_cases.ledger import (
    CreateAccount,
    CreateCurrency,
    GetTradingBalanceDetailedDTOs,
    GetTradingBalanceRawDTOs,
    PostTransaction,
)
from py_accountant.infrastructure.persistence.inmemory.uow import InMemoryUnitOfWork


def _seed_basic(uow: InMemoryUnitOfWork) -> None:
    CreateCurrency(uow)("USD", exchange_rate=Decimal("1"))
    CreateCurrency(uow)("EUR", exchange_rate=Decimal("1.1"))
    CreateAccount(uow)("Assets:CashUSD", "USD")
    CreateAccount(uow)("Assets:CashEUR", "EUR")
    CreateAccount(uow)("Income:Sales", "USD")
    clock_ts = datetime.now(UTC)
    clock = type("_Clock", (), {"now": lambda self: clock_ts})()
    post = PostTransaction(uow, clock)
    post([
        # USD sale 100
        EntryLineDTO(side="DEBIT", account_full_name="Assets:CashUSD", amount=Decimal("100"), currency_code="USD"),
        EntryLineDTO(side="CREDIT", account_full_name="Income:Sales", amount=Decimal("100"), currency_code="USD"),
    ])
    post([
        # EUR sale 50 EUR (with explicit rate) ~ 55 USD
        EntryLineDTO(side="DEBIT", account_full_name="Assets:CashEUR", amount=Decimal("50"), currency_code="EUR", exchange_rate=Decimal("1.1")),
        EntryLineDTO(side="CREDIT", account_full_name="Income:Sales", amount=Decimal("50"), currency_code="EUR", exchange_rate=Decimal("1.1")),
    ])


def test_raw_use_case_returns_simple_dto() -> None:
    uow = InMemoryUnitOfWork()
    _seed_basic(uow)
    raw_uc = GetTradingBalanceRawDTOs(uow, type("_Clock", (), {"now": lambda self: datetime.now(UTC)})())
    lines = raw_uc()
    assert lines and all(isinstance(line, TradingBalanceLineSimple) for line in lines)
    # Simple DTO must not have base conversion attributes
    for line in lines:
        assert not hasattr(line, "debit_base")
        assert not hasattr(line, "credit_base")
        assert not hasattr(line, "net_base")


def test_detailed_use_case_returns_detailed_dto() -> None:
    uow = InMemoryUnitOfWork()
    _seed_basic(uow)
    det_uc = GetTradingBalanceDetailedDTOs(uow, type("_Clock", (), {"now": lambda self: datetime.now(UTC)})())
    lines = det_uc("USD")
    assert lines and all(isinstance(line, TradingBalanceLineDetailed) for line in lines)
    for line in lines:
        assert line.base_currency_code == "USD"
        assert line.debit_base >= Decimal("0")
        assert line.used_rate >= Decimal("1")


def test_no_converted_fields_in_simple_output() -> None:
    uow = InMemoryUnitOfWork()
    _seed_basic(uow)
    type("_Clock", (), {"now": lambda self: datetime.now(UTC)})()
    field_names = {f.name for f in getattr(TradingBalanceLineSimple, "__dataclass_fields__", {}).values()}
    assert "debit_base" not in field_names and "credit_base" not in field_names and "net_base" not in field_names
