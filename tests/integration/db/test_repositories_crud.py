from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from application.dto.models import AccountDTO, CurrencyDTO
from infrastructure.persistence.sqlalchemy.models import Base
from infrastructure.persistence.sqlalchemy.repositories_async import (
    AsyncSqlAlchemyAccountRepository,
    AsyncSqlAlchemyCurrencyRepository,
)


@pytest.mark.asyncio
async def test_currency_crud():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with Session() as session:
        repo = AsyncSqlAlchemyCurrencyRepository(session)
        # Create two currencies
        await repo.upsert(CurrencyDTO(code="USD", is_base=True))
        await repo.upsert(CurrencyDTO(code="EUR", exchange_rate=Decimal("0.9")))
        # Get by code
        usd = await repo.get_by_code("USD")
        eur = await repo.get_by_code("EUR")
        assert usd and usd.is_base
        assert eur and eur.exchange_rate == Decimal("0.9")
        # List all
        lst = await repo.list_all()
        assert {c.code for c in lst} >= {"USD", "EUR"}
        # Update rate
        await repo.upsert(CurrencyDTO(code="EUR", exchange_rate=Decimal("0.95")))
        eur2 = await repo.get_by_code("EUR")
        assert eur2 and eur2.exchange_rate == Decimal("0.95")
        # Change base
        await repo.set_base("EUR")
        eur_base = await repo.get_base()
        assert eur_base and eur_base.code == "EUR"
        # Delete USD
        deleted = await repo.delete("USD")
        assert deleted
        missing = await repo.get_by_code("USD")
        assert missing is None


@pytest.mark.asyncio
async def test_account_crud():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with Session() as session:
        cur_repo = AsyncSqlAlchemyCurrencyRepository(session)
        acc_repo = AsyncSqlAlchemyAccountRepository(session)
        await cur_repo.upsert(CurrencyDTO(code="USD", is_base=True))
        # Create account
        dto = AccountDTO(id="", name="Cash", full_name="Assets:Cash", currency_code="USD", parent_id=None)
        created = await acc_repo.create(dto)
        assert created.id
        # Get by full name
        fetched = await acc_repo.get_by_full_name("Assets:Cash")
        assert fetched and fetched.id == created.id
        # List accounts
        all_acc = await acc_repo.list()
        assert any(a.full_name == "Assets:Cash" for a in all_acc)
        # Delete
        deleted = await acc_repo.delete("Assets:Cash")
        assert deleted
        missing = await acc_repo.get_by_full_name("Assets:Cash")
        assert missing is None

