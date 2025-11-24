from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import select

from py_accountant.application.dto.models import EntryLineDTO, TransactionDTO
from py_accountant.infrastructure.persistence.sqlalchemy.models import (
    AccountBalanceORM,
    AccountDailyTurnoverORM,
    Base,
    JournalORM,
    TransactionLineORM,
)
from py_accountant.infrastructure.persistence.sqlalchemy.uow import AsyncSqlAlchemyUnitOfWork


@pytest.mark.asyncio
async def test_repository_upserts_balance(async_uow: AsyncSqlAlchemyUnitOfWork) -> None:
    """Posting mixed debit/credit lines обновляет denormalized balance (account_balances)."""
    repo = async_uow.transactions

    async def post(lines: list[EntryLineDTO]) -> None:
        dto = TransactionDTO(
            id="t1",
            occurred_at=datetime.now(UTC),
            lines=lines,
            memo=None,
            meta={},
        )
        await repo.add(dto)

    await post([EntryLineDTO(side="DEBIT", account_full_name="Assets:Cash", amount=Decimal("100"), currency_code="USD", exchange_rate=None)])
    await post([EntryLineDTO(side="CREDIT", account_full_name="Assets:Cash", amount=Decimal("40"), currency_code="USD", exchange_rate=None)])
    await post([EntryLineDTO(side="DEBIT", account_full_name="Assets:Cash", amount=Decimal("10"), currency_code="USD", exchange_rate=None)])

    res = await async_uow.session.execute(select(AccountBalanceORM).where(AccountBalanceORM.account_full_name == "Assets:Cash"))
    row = res.scalar_one()
    assert row.balance == Decimal("70"), "Balance must accumulate DEBIT - CREDIT (100 - 40 + 10)."


@pytest.mark.asyncio
async def test_repository_upserts_turnover_same_day_multiple_lines(async_uow: AsyncSqlAlchemyUnitOfWork) -> None:
    """Multiple postings в один день агрегируются в одну строку account_daily_turnovers."""
    repo = async_uow.transactions

    async def post(lines: list[EntryLineDTO]) -> None:
        dto = TransactionDTO(
            id="t2",
            occurred_at=datetime.now(UTC),
            lines=lines,
            memo=None,
            meta={},
        )
        await repo.add(dto)

    await post([EntryLineDTO(side="DEBIT", account_full_name="Assets:Cash", amount=Decimal("25"), currency_code="USD", exchange_rate=None)])
    await post([
        EntryLineDTO(side="DEBIT", account_full_name="Assets:Cash", amount=Decimal("5"), currency_code="USD", exchange_rate=None),
        EntryLineDTO(side="CREDIT", account_full_name="Assets:Cash", amount=Decimal("2"), currency_code="USD", exchange_rate=None),
    ])
    await post([EntryLineDTO(side="CREDIT", account_full_name="Assets:Cash", amount=Decimal("8"), currency_code="USD", exchange_rate=None)])

    res = await async_uow.session.execute(select(AccountDailyTurnoverORM).where(AccountDailyTurnoverORM.account_full_name == "Assets:Cash"))
    rows = res.scalars().all()
    assert len(rows) == 1, "All turnovers for same UTC day must collapse into a single row."
    r = rows[0]
    assert r.debit_total == Decimal("30") and r.credit_total == Decimal("10"), "Turnover totals must sum line debits/credits (25+5, 2+8)."


@pytest.mark.asyncio
async def test_repository_concurrent_postings_consistent_balance(tmp_path) -> None:
    """Concurrent postings (отдельные сессии) должны привести к корректной итоговой сумме (гарантия race-safety).

    Примечание: SQLite не поддерживает полноценные конкурентные записи без WAL и тонкой настройки таймаутов,
    поэтому тест пропускается на sqlite.
    """
    db_path = tmp_path / "concurrency.db"
    url = f"sqlite+aiosqlite:///{db_path}"

    # Bootstrap schema via one UoW
    init_uow = AsyncSqlAlchemyUnitOfWork(url)
    async with init_uow.engine.begin() as conn:  # type: ignore[attr-defined]
        await conn.run_sync(Base.metadata.create_all)

    # Skip on SQLite due to database is locked under concurrent writes
    if "sqlite" in str(init_uow.engine.url):  # type: ignore[attr-defined]
        pytest.skip("Concurrent write test is skipped on SQLite (database is locked). Run on Postgres in integration suite.")

    async def worker(idx: int) -> None:
        uow = AsyncSqlAlchemyUnitOfWork(url)
        async with uow:  # open transaction
            repo = uow.transactions
            dto = TransactionDTO(
                id=f"c{idx}",
                occurred_at=datetime.now(UTC),
                lines=[EntryLineDTO(side="DEBIT", account_full_name="Assets:Cash", amount=Decimal("1"), currency_code="USD", exchange_rate=None)],
                memo=None,
                meta={},
            )
            await repo.add(dto)

    await asyncio.gather(*[worker(i) for i in range(50)])

    check_uow = AsyncSqlAlchemyUnitOfWork(url)
    async with check_uow:
        res = await check_uow.session.execute(select(AccountBalanceORM).where(AccountBalanceORM.account_full_name == "Assets:Cash"))
        row = res.scalar_one()
        assert row.balance == Decimal("50"), "Concurrent postings must not lose/duplicate increments."


@pytest.mark.asyncio
async def test_get_balance_fallback_zero_when_missing(async_uow: AsyncSqlAlchemyUnitOfWork) -> None:
    """Вызов get_balance для счёта без транзакций возвращает Decimal('0')."""
    acct_repo = async_uow.accounts
    bal = await acct_repo.get_balance("Expenses:New")
    assert bal == Decimal("0")


@pytest.mark.asyncio
async def test_get_balance_matches_legacy_scan(async_uow: AsyncSqlAlchemyUnitOfWork) -> None:
    """Aggregated баланс должен совпадать с суммой DEBIT - CREDIT из строк журнала (legacy scan)."""
    tx_repo = async_uow.transactions
    acct_repo = async_uow.accounts

    async def post(lines: list[EntryLineDTO]) -> None:
        dto = TransactionDTO(
            id="scan",
            occurred_at=datetime.now(UTC),
            lines=lines,
            memo=None,
            meta={},
        )
        await tx_repo.add(dto)

    await post([EntryLineDTO(side="DEBIT", account_full_name="Assets:Cash", amount=Decimal("10"), currency_code="USD", exchange_rate=None)])
    await post([EntryLineDTO(side="CREDIT", account_full_name="Assets:Cash", amount=Decimal("3"), currency_code="USD", exchange_rate=None)])
    await post([EntryLineDTO(side="DEBIT", account_full_name="Assets:Cash", amount=Decimal("2"), currency_code="USD", exchange_rate=None)])

    fast = await acct_repo.get_balance("Assets:Cash")

    res = await async_uow.session.execute(
        select(TransactionLineORM.side, TransactionLineORM.amount)
        .join(JournalORM, JournalORM.id == TransactionLineORM.journal_id)
        .where(TransactionLineORM.account_full_name == "Assets:Cash")
    )
    legacy_rows = res.all()
    legacy = Decimal("0")
    for side, amount in legacy_rows:
        legacy += amount if side == "DEBIT" else -amount  # type: ignore[operator]

    assert fast == legacy == Decimal("9"), "Fast aggregate balance must equal legacy scan (10 - 3 + 2)."
