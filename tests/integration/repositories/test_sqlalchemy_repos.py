from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import cast

import pytest


@pytest.mark.xfail(reason="REWRITE-DOMAIN (I13): account balance moved out of repositories", strict=False)
async def test_async_sqlalchemy_uow_post_and_query(tmp_path):
    """Async UoW: create entities, post tx, verify balance and ledger list."""
    db_path = tmp_path / "async_repo.sqlite3"
    url = f"sqlite+aiosqlite:///{db_path}"
    uow: AsyncUoWProtocol = cast(AsyncUoWProtocol, AsyncSqlAlchemyUnitOfWork(url=url))

    from infrastructure.persistence.sqlalchemy.models import Base  # type: ignore
    async with cast(AsyncSqlAlchemyUnitOfWork, uow).engine.begin() as conn:  # type: ignore[attr-defined]
        await conn.run_sync(Base.metadata.create_all)

    clock = FixedClock(datetime.now(UTC))

    async with uow:
        await AsyncCreateCurrency(uow)("USD", exchange_rate=Decimal("1"))
        await AsyncCreateAccount(uow)("Assets:Cash", "USD")
        await AsyncCreateAccount(uow)("Income:Sales", "USD")
        post = AsyncPostTransaction(uow, clock)
        await post([
            EntryLineDTO(side="DEBIT", account_full_name="Assets:Cash", amount=Decimal("10"), currency_code="USD"),
            EntryLineDTO(side="CREDIT", account_full_name="Income:Sales", amount=Decimal("10"), currency_code="USD"),
        ])
        await uow.commit()

    async with uow:
        bal = await AsyncGetAccountBalance(uow, clock)("Assets:Cash")
        assert bal == Decimal("10")
        led = await AsyncGetLedger(uow, clock)("Assets:Cash")
        assert len(led) == 1
