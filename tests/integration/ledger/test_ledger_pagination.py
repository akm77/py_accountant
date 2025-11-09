from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from application.dto.models import EntryLineDTO
from application.use_cases.ledger import CreateAccount, CreateCurrency, ListLedger, PostTransaction
from infrastructure.persistence.inmemory.clock import FixedClock
from infrastructure.persistence.sqlalchemy.uow import SqlAlchemyUnitOfWork


def seed(uow, clock):
    CreateCurrency(uow)("USD", exchange_rate=Decimal("1"))
    CreateAccount(uow)("Assets:Cash", "USD")
    CreateAccount(uow)("Income:Sales", "USD")
    post = PostTransaction(uow, clock)
    base = clock.now()
    for i in range(5):
        occurred = base + timedelta(seconds=i)
        # FixedClock stores value in _fixed
        clock._fixed = occurred  # type: ignore[attr-defined]
        meta = {"kind": "sale" if i % 2 == 0 else "refund"}
        post([
            EntryLineDTO(side="DEBIT", account_full_name="Assets:Cash", amount=Decimal(str(10 + i)), currency_code="USD"),
            EntryLineDTO(side="CREDIT", account_full_name="Income:Sales", amount=Decimal(str(10 + i)), currency_code="USD"),
        ], memo=f"tx{i}", meta=meta)


def test_pagination_and_order_and_meta():
    uow = SqlAlchemyUnitOfWork(url="sqlite+pysqlite:///:memory:")
    clock = FixedClock(datetime.now(UTC))
    seed(uow, clock)

    ll = ListLedger(uow, clock)

    # Order ASC default, limit 2
    asc_two = ll("Assets:Cash", limit=2)
    assert len(asc_two) == 2
    assert asc_two[0].memo == "tx0" and asc_two[1].memo == "tx1"

    # Offset 3 should return last two
    last_two = ll("Assets:Cash", offset=3)
    assert len(last_two) == 2
    assert last_two[0].memo == "tx3" and last_two[1].memo == "tx4"

    # Order DESC
    desc_two = ll("Assets:Cash", limit=2, order="DESC")
    assert len(desc_two) == 2
    # Verify occurred_at descending
    assert desc_two[0].occurred_at >= desc_two[1].occurred_at
    # Top two should be tx4 and tx3
    assert {desc_two[0].memo, desc_two[1].memo} == {"tx4", "tx3"}

    # Meta filter kind=sale -> tx0, tx2, tx4
    only_sales = ll("Assets:Cash", meta={"kind": "sale"})
    assert [t.memo for t in only_sales] == ["tx0", "tx2", "tx4"]

    # Offset greater than total -> empty
    empty = ll("Assets:Cash", offset=10)
    assert empty == []

    # Limit 0 -> empty
    assert ll("Assets:Cash", limit=0) == []
