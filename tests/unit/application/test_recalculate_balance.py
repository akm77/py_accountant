from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from application.dto.models import EntryLineDTO
from application.use_cases.ledger import CreateAccount, CreateCurrency, GetBalance, PostTransaction
from application.use_cases.recalculate import RecalculateAccountBalance
from domain.services.account_balance_service import InMemoryAccountBalanceService
from infrastructure.persistence.inmemory.clock import FixedClock
from infrastructure.persistence.inmemory.uow import InMemoryUnitOfWork


def test_recalculate_inmemory_matches_direct():
    now = datetime.now(UTC)
    clock = FixedClock(now)
    uow = InMemoryUnitOfWork()

    CreateCurrency(uow)("USD")
    CreateAccount(uow)("Assets:Cash", "USD")
    CreateAccount(uow)("Income:Sales", "USD")

    post = PostTransaction(uow, clock)
    post([
        EntryLineDTO(side="DEBIT", account_full_name="Assets:Cash", amount=Decimal("50"), currency_code="USD"),
        EntryLineDTO(side="CREDIT", account_full_name="Income:Sales", amount=Decimal("50"), currency_code="USD"),
    ])

    svc = InMemoryAccountBalanceService()
    get_balance = GetBalance(uow, clock, balance_service=svc)
    recalc = RecalculateAccountBalance(uow, clock, balance_service=svc)

    # Initial read warms cache
    bal1 = get_balance("Assets:Cash")
    # Add another transaction in the future and recompute to now
    post([
        EntryLineDTO(side="DEBIT", account_full_name="Assets:Cash", amount=Decimal("25"), currency_code="USD"),
        EntryLineDTO(side="CREDIT", account_full_name="Income:Sales", amount=Decimal("25"), currency_code="USD"),
    ])
    bal2 = recalc("Assets:Cash")
    assert bal2 == get_balance("Assets:Cash")


def test_recalculate_direct_aggregation_without_service():
    now = datetime.now(UTC)
    clock = FixedClock(now)
    uow = InMemoryUnitOfWork()

    CreateCurrency(uow)("USD")
    CreateAccount(uow)("Assets:Cash", "USD")
    CreateAccount(uow)("Income:Sales", "USD")

    post = PostTransaction(uow, clock)
    post([
        EntryLineDTO(side="DEBIT", account_full_name="Assets:Cash", amount=Decimal("10"), currency_code="USD"),
        EntryLineDTO(side="CREDIT", account_full_name="Income:Sales", amount=Decimal("10"), currency_code="USD"),
    ])

    recalc = RecalculateAccountBalance(uow, clock)
    # Should equal a direct repository aggregation
    direct = uow.transactions.account_balance("Assets:Cash", clock.now())
    assert recalc("Assets:Cash") == direct

