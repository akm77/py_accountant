from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from application.dto.models import EntryLineDTO
from application.use_cases.ledger import (
    CreateAccount,
    CreateCurrency,
    GetBalance,
    GetLedger,
    PostTransaction,
)
from infrastructure.persistence.inmemory.clock import FixedClock
from infrastructure.persistence.sqlalchemy.uow import SqlAlchemyUnitOfWork


def test_sqlalchemy_uow_post_and_query():
    uow = SqlAlchemyUnitOfWork(url="sqlite+pysqlite:///:memory:")
    # Setup
    CreateCurrency(uow)("USD", exchange_rate=Decimal("1"))
    CreateAccount(uow)("Assets:Cash", "USD")
    CreateAccount(uow)("Income:Sales", "USD")
    clock = FixedClock(datetime.now(UTC))
    post = PostTransaction(uow, clock)
    post([
        EntryLineDTO(side="DEBIT", account_full_name="Assets:Cash", amount=Decimal("10"), currency_code="USD"),
        EntryLineDTO(side="CREDIT", account_full_name="Income:Sales", amount=Decimal("10"), currency_code="USD"),
    ])
    # Balance
    bal = GetBalance(uow, clock)("Assets:Cash")
    assert bal == Decimal("10")
    # Ledger
    led = GetLedger(uow, clock)("Assets:Cash")
    assert len(led) == 1

