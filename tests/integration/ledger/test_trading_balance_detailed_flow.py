from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from application.dto.models import EntryLineDTO
from application.use_cases.ledger import CreateAccount, CreateCurrency, GetTradingBalanceDetailed, PostTransaction
from infrastructure.persistence.inmemory.clock import FixedClock
from infrastructure.persistence.sqlalchemy.uow import SqlAlchemyUnitOfWork


def test_trading_balance_detailed_flow_sqlalchemy(tmp_path):
    # Use file sqlite to persist across UoW instances
    db_url = f"sqlite+pysqlite:///{tmp_path}/test.db"
    uow = SqlAlchemyUnitOfWork(url=db_url)
    clock = FixedClock(fixed=datetime.now(UTC))

    CreateCurrency(uow)("USD", exchange_rate=Decimal("1"))
    CreateCurrency(uow)("EUR", exchange_rate=Decimal("1.25"))
    CreateAccount(uow)("Assets:Cash", "USD")
    CreateAccount(uow)("Assets:BankEUR", "EUR")
    CreateAccount(uow)("Income:Sales", "USD")

    post = PostTransaction(uow, clock)
    post([
        EntryLineDTO(side="DEBIT", account_full_name="Assets:Cash", amount=Decimal("200"), currency_code="USD"),
        EntryLineDTO(side="CREDIT", account_full_name="Income:Sales", amount=Decimal("200"), currency_code="USD"),
    ])
    post([
        EntryLineDTO(side="DEBIT", account_full_name="Assets:BankEUR", amount=Decimal("100"), currency_code="EUR"),
        EntryLineDTO(side="CREDIT", account_full_name="Income:Sales", amount=Decimal("100"), currency_code="EUR"),
    ])

    tb = GetTradingBalanceDetailed(uow, clock)("USD")
    assert tb.base_currency == "USD"
    assert all(l.converted_balance is not None for l in tb.lines)
    base_total = sum(l.converted_balance for l in tb.lines)  # type: ignore[arg-type]
    assert tb.base_total == base_total

