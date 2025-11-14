from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from application.dto.models import AccountDTO, CurrencyDTO, EntryLineDTO, TransactionDTO
from infrastructure.persistence.inmemory.clock import FixedClock
from infrastructure.persistence.inmemory.repositories import (
    InMemoryAccountRepository,
    InMemoryCurrencyRepository,
    InMemoryTransactionRepository,
)
from infrastructure.persistence.inmemory.uow import InMemoryUnitOfWork


def test_inmemory_currency_repo() -> None:
    repo = InMemoryCurrencyRepository()
    assert repo.get_by_code("USD") is None
    repo.upsert(CurrencyDTO(code="USD", name="US Dollar", precision=2))
    assert repo.get_by_code("USD") is not None
    assert len(repo.list_all()) == 1


def test_inmemory_account_repo() -> None:
    repo = InMemoryAccountRepository()
    acc = AccountDTO(id="a1", name="Cash", full_name="Assets:Cash", currency_code="USD")
    repo.create(acc)
    assert repo.get_by_full_name("Assets:Cash") == acc
    assert repo.list() and repo.list()[0].id == "a1"


def test_inmemory_transaction_repo_balance() -> None:
    repo = InMemoryTransactionRepository()
    now = datetime.now(UTC)
    line1 = EntryLineDTO(side="DEBIT", account_full_name="Assets:Cash", amount=Decimal("25.00"), currency_code="USD")
    line2 = EntryLineDTO(side="CREDIT", account_full_name="Income:Sales", amount=Decimal("25.00"), currency_code="USD")
    repo.add(TransactionDTO(id="t1", occurred_at=now - timedelta(minutes=1), lines=[line1, line2]))
    bal = repo.account_balance("Assets:Cash", now)
    assert bal == Decimal("25.00")


def test_inmemory_uow_basic() -> None:
    uow = InMemoryUnitOfWork()
    uow.currencies.upsert(CurrencyDTO(code="EUR", name="Euro", precision=2))
    uow.accounts.create(AccountDTO(id="a2", name="Bank", full_name="Assets:Bank", currency_code="EUR"))
    now = datetime.now(UTC)
    l1 = EntryLineDTO(side="DEBIT", account_full_name="Assets:Bank", amount=Decimal("10.00"), currency_code="EUR")
    l2 = EntryLineDTO(side="CREDIT", account_full_name="Income:Sales", amount=Decimal("10.00"), currency_code="EUR")
    uow.transactions.add(TransactionDTO(id="tx", occurred_at=now, lines=[l1, l2]))
    uow.commit()  # no-op
    # Verify ledger returns rich DTOs including our transaction
    rows = uow.transactions.ledger("Assets:Bank", now - timedelta(days=1), now + timedelta(days=1))
    assert rows and rows[0].id.startswith("journal:") or rows[0].id == "tx"


def test_fixed_clock() -> None:
    fixed_time = datetime(2025, 1, 1, tzinfo=UTC)
    clock = FixedClock(fixed=fixed_time)
    assert clock.now() == fixed_time
