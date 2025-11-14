from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from application.dto.models import EntryLineDTO
from application.use_cases.ledger import (
    CreateAccount,
    CreateCurrency,
    GetBalance,
    GetTradingBalanceDetailedDTOs,
    PostTransaction,
)
from infrastructure.persistence.inmemory.clock import FixedClock
from infrastructure.persistence.inmemory.uow import InMemoryUnitOfWork


def test_create_currency_and_account_happy_path_use_cases():
    uow = InMemoryUnitOfWork()
    CreateCurrency(uow)("USD")
    acc = CreateAccount(uow)("Assets:Cash", "USD")
    assert acc.full_name == "Assets:Cash"
    assert uow.accounts.get_by_full_name("Assets:Cash") is not None


def test_post_transaction_and_balance_use_cases():
    now = datetime.now(UTC)
    clock = FixedClock(now)
    uow = InMemoryUnitOfWork()

    CreateCurrency(uow)("USD")
    CreateAccount(uow)("Assets:Cash", "USD")
    CreateAccount(uow)("Income:Sales", "USD")

    post = PostTransaction(uow, clock)
    post([
        EntryLineDTO(side="DEBIT", account_full_name="Assets:Cash", amount=Decimal("100"), currency_code="USD"),
        EntryLineDTO(side="CREDIT", account_full_name="Income:Sales", amount=Decimal("100"), currency_code="USD"),
    ])

    bal = GetBalance(uow, clock)("Assets:Cash")
    assert bal == Decimal("100")


def test_trading_balance_detailed_use_case_with_rates():
    now = datetime.now(UTC)
    clock = FixedClock(now)
    uow = InMemoryUnitOfWork()

    # Base and foreign
    CreateCurrency(uow)("USD")
    eur = CreateCurrency(uow)("EUR")
    # Set base explicitly by repository helper
    uow.currencies.set_base("USD")
    # Update EUR rate via upsert
    eur.exchange_rate = Decimal("1.25")
    uow.currencies.upsert(eur)

    CreateAccount(uow)("Assets:Cash", "USD")
    CreateAccount(uow)("Income:Sales", "EUR")

    post = PostTransaction(uow, clock)
    post([
        EntryLineDTO(side="DEBIT", account_full_name="Assets:Cash", amount=Decimal("100"), currency_code="USD"),
        EntryLineDTO(side="CREDIT", account_full_name="Income:Sales", amount=Decimal("125"), currency_code="EUR", exchange_rate=Decimal("1.25")),
    ])

    lines = GetTradingBalanceDetailedDTOs(uow, clock)("USD")
    # EUR used_rate should be 1.25 (rate_quantize to 6 d.p.)
    found_eur = next((l for l in lines if l.currency_code == "EUR"), None)
    assert found_eur is not None
    assert found_eur.used_rate == Decimal("1.25")
