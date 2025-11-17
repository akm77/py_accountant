from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from application.dto.models import EntryLineDTO
from application.use_cases.ledger import CreateAccount, CreateCurrency, ListLedger, PostTransaction
from domain import DomainError
from infrastructure.persistence.inmemory.clock import FixedClock
from infrastructure.persistence.inmemory.uow import InMemoryUnitOfWork


def setup():
    uow = InMemoryUnitOfWork()
    CreateCurrency(uow)("USD", exchange_rate=Decimal("1"))
    CreateAccount(uow)("Assets:Cash", "USD")
    CreateAccount(uow)("Income:Sales", "USD")
    clock = FixedClock(datetime.now(UTC))
    post = PostTransaction(uow, clock)
    post([
        EntryLineDTO(side="DEBIT", account_full_name="Assets:Cash", amount=Decimal("10"), currency_code="USD"),
        EntryLineDTO(side="CREDIT", account_full_name="Income:Sales", amount=Decimal("10"), currency_code="USD"),
    ], meta={"kind": "sale"})
    return uow, clock


def test_invalid_account_name():
    uow, clock = setup()
    ll = ListLedger(uow, clock)
    with pytest.raises(DomainError):
        ll("Cash", offset=0)


def test_start_greater_than_end():
    uow, clock = setup()
    ll = ListLedger(uow, clock)
    now = clock.now()
    with pytest.raises(DomainError):
        ll("Assets:Cash", start=now + timedelta(seconds=10), end=now)


def test_negative_offset():
    uow, clock = setup()
    ll = ListLedger(uow, clock)
    with pytest.raises(DomainError):
        ll("Assets:Cash", offset=-1)


def test_negative_limit():
    uow, clock = setup()
    ll = ListLedger(uow, clock)
    with pytest.raises(DomainError):
        ll("Assets:Cash", limit=-5)


def test_invalid_order():
    uow, clock = setup()
    ll = ListLedger(uow, clock)
    with pytest.raises(DomainError):
        ll("Assets:Cash", order="DOWN")


def test_meta_not_dict():
    uow, clock = setup()
    ll = ListLedger(uow, clock)
    with pytest.raises(DomainError):
        ll("Assets:Cash", meta=123)  # type: ignore[arg-type]


def test_limit_zero_returns_empty():
    uow, clock = setup()
    ll = ListLedger(uow, clock)
    res = ll("Assets:Cash", limit=0)
    assert res == []

