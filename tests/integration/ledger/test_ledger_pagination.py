from __future__ import annotations  # noqa: I001

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import cast

import pytest

from py_accountant.application.dto.models import EntryLineDTO
from py_accountant.application.use_cases_async import (
    AsyncCreateCurrency,
    AsyncSetBaseCurrency,
    AsyncCreateAccount,
    AsyncPostTransaction,
    AsyncGetLedger,
)
from py_accountant.infrastructure.persistence.inmemory.clock import FixedClock
from py_accountant.infrastructure.persistence.sqlalchemy.models import Base
from py_accountant.infrastructure.persistence.sqlalchemy.uow import AsyncSqlAlchemyUnitOfWork


async def seed(uow, clock):
    await AsyncCreateCurrency(uow)("USD", exchange_rate=Decimal("1"))
    # Set USD as base to satisfy domain ledger validation
    await AsyncSetBaseCurrency(uow)("USD")
    await AsyncCreateAccount(uow)("Assets:Cash", "USD")
    await AsyncCreateAccount(uow)("Income:Sales", "USD")
    post = AsyncPostTransaction(uow, clock)
    base = clock.now()
    for i in range(5):
        occurred = base + timedelta(seconds=i)
        clock._fixed = occurred  # type: ignore[attr-defined]
        meta = {"kind": "sale" if i % 2 == 0 else "refund"}
        await post([
            EntryLineDTO(side="DEBIT", account_full_name="Assets:Cash", amount=Decimal(str(10 + i)), currency_code="USD"),
            EntryLineDTO(side="CREDIT", account_full_name="Income:Sales", amount=Decimal(str(10 + i)), currency_code="USD"),
        ], memo=f"tx{i}", meta=meta)



@pytest.mark.asyncio
async def test_pagination_and_order_and_meta_async(tmp_path):
    db_path = tmp_path / "ledger.sqlite3"
    url = f"sqlite+aiosqlite:///{db_path}"
    uow = AsyncSqlAlchemyUnitOfWork(url=url)


    async with cast(AsyncSqlAlchemyUnitOfWork, uow).engine.begin() as conn:  # type: ignore[attr-defined]
        await conn.run_sync(Base.metadata.create_all)

    clock = FixedClock(datetime.now(UTC))
    async with uow:
        await seed(uow, clock)
        await uow.commit()

    async with uow:
        ll = AsyncGetLedger(uow, clock)
        asc_two = await ll("Assets:Cash", limit=2)
        assert len(asc_two) == 2
        assert asc_two[0].memo == "tx0" and asc_two[1].memo == "tx1"

        last_two = await ll("Assets:Cash", offset=3)
        assert len(last_two) == 2
        assert last_two[0].memo == "tx3" and last_two[1].memo == "tx4"

        desc_two = await ll("Assets:Cash", limit=2, order="DESC")
        assert len(desc_two) == 2
        assert desc_two[0].occurred_at >= desc_two[1].occurred_at
        assert {desc_two[0].memo, desc_two[1].memo} == {"tx4", "tx3"}

        only_sales = await ll("Assets:Cash", meta={"kind": "sale"})
        assert [t.memo for t in only_sales] == ["tx0", "tx2", "tx4"]

        empty = await ll("Assets:Cash", offset=10)
        assert empty == []

        assert await ll("Assets:Cash", limit=0) == []
