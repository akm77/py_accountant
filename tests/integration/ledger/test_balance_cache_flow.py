from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from application.dto.models import EntryLineDTO
from application.use_cases.ledger import CreateAccount, CreateCurrency, GetBalance, PostTransaction
from domain.services.account_balance_service import SqlAccountBalanceService
from infrastructure.persistence.inmemory.clock import FixedClock
from infrastructure.persistence.sqlalchemy.uow import SqlAlchemyUnitOfWork


def test_sql_balance_cache_flow_increment_and_recompute():
    uow = SqlAlchemyUnitOfWork(url="sqlite+pysqlite:///:memory:")
    clock = FixedClock(datetime.now(UTC))
    CreateCurrency(uow)("USD", exchange_rate=Decimal("1"))
    CreateAccount(uow)("Assets:Cash", "USD")
    CreateAccount(uow)("Income:Sales", "USD")

    balance_service = SqlAccountBalanceService(transactions=uow.transactions, balances=uow.balances)
    post = PostTransaction(uow, clock, balance_service=balance_service)

    # First transaction
    post([
        EntryLineDTO(side="DEBIT", account_full_name="Assets:Cash", amount=Decimal("50"), currency_code="USD"),
        EntryLineDTO(side="CREDIT", account_full_name="Income:Sales", amount=Decimal("50"), currency_code="USD"),
    ])
    bal_uc = GetBalance(uow, clock, balance_service=balance_service)
    bal1 = bal_uc("Assets:Cash")
    assert bal1 == Decimal("50")

    # Second transaction 20 credit reduces to 30
    clock.fixed = clock.now() + timedelta(seconds=5)
    post([
        EntryLineDTO(side="CREDIT", account_full_name="Assets:Cash", amount=Decimal("20"), currency_code="USD"),
        EntryLineDTO(side="DEBIT", account_full_name="Income:Sales", amount=Decimal("20"), currency_code="USD"),
    ])
    bal2 = bal_uc("Assets:Cash")
    assert bal2 == Decimal("30")

    # Force recompute (should match direct balance)
    recomputed = bal_uc("Assets:Cash", recompute=True)
    assert recomputed == Decimal("30")

    # Advance time and request balance as_of earlier than cache -> recompute path returns same
    earlier = clock.now() - timedelta(seconds=10)
    bal_earlier = bal_uc("Assets:Cash", as_of=earlier, recompute=True)
    assert bal_earlier == Decimal("0")

