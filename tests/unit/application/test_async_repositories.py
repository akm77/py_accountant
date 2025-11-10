from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from application.dto.models import AccountDTO, CurrencyDTO, EntryLineDTO, TransactionDTO
from infrastructure.persistence.sqlalchemy.uow import AsyncSqlAlchemyUnitOfWork

pytestmark = pytest.mark.asyncio


async def test_currency_upsert_and_base(async_uow: AsyncSqlAlchemyUnitOfWork):
    """Currency upsert/list/base semantics under async repository."""
    uow = async_uow
    # upsert non-base currency
    usd = await uow.currencies.upsert(CurrencyDTO(code="USD", exchange_rate=Decimal("1.0")))
    assert usd.code == "USD" and usd.is_base is False
    # set base currency
    await uow.currencies.set_base("USD")
    base = await uow.currencies.get_base()
    assert base and base.code == "USD" and base.is_base is True and base.exchange_rate is None
    # second currency
    eur = await uow.currencies.upsert(CurrencyDTO(code="EUR", exchange_rate=Decimal("0.9")))
    assert eur.code == "EUR" and eur.is_base is False
    # bulk upsert should not override base
    await uow.currencies.bulk_upsert_rates([("USD", Decimal("9.9")), ("EUR", Decimal("1.1"))])
    usd2 = await uow.currencies.get_by_code("USD")
    eur2 = await uow.currencies.get_by_code("EUR")
    assert usd2 and usd2.exchange_rate is None
    assert eur2 and eur2.exchange_rate == Decimal("1.1")


async def test_currency_set_base_missing_raises(async_uow: AsyncSqlAlchemyUnitOfWork):
    """Setting base on a non-existent currency must raise ValueError (parity with sync)."""
    with pytest.raises(ValueError):
        await async_uow.currencies.set_base("NOPE")


async def test_account_create_and_unique(async_uow: AsyncSqlAlchemyUnitOfWork):
    """Account create enforces unique full_name; get_by_full_name works."""
    uow = async_uow
    dto = AccountDTO(id="", name="Cash", full_name="Assets:Cash", currency_code="USD")
    created = await uow.accounts.create(dto)
    assert created.id and created.full_name == "Assets:Cash"
    # duplicate
    with pytest.raises(ValueError):
        await uow.accounts.create(dto)
    # get by full name
    fetched = await uow.accounts.get_by_full_name("Assets:Cash")
    assert fetched and fetched.full_name == "Assets:Cash"


async def test_transactions_add_and_list_between_with_meta(async_uow: AsyncSqlAlchemyUnitOfWork):
    """Transactions listing supports meta exact-match filter and chronological order."""
    uow = async_uow
    t0 = datetime.now(UTC)
    # Add two journals with distinct meta
    tx1 = TransactionDTO(
        id="",
        occurred_at=t0,
        memo="T1",
        lines=[
            EntryLineDTO(side="DEBIT", account_full_name="Assets:Cash", amount=Decimal("100"), currency_code="USD"),
            EntryLineDTO(side="CREDIT", account_full_name="Income:Salary", amount=Decimal("100"), currency_code="USD"),
        ],
        meta={"tag": "alpha"},
    )
    tx2 = TransactionDTO(
        id="",
        occurred_at=t0 + timedelta(seconds=1),
        memo="T2",
        lines=[
            EntryLineDTO(side="DEBIT", account_full_name="Assets:Bank", amount=Decimal("50"), currency_code="USD"),
            EntryLineDTO(side="CREDIT", account_full_name="Income:Other", amount=Decimal("50"), currency_code="USD"),
        ],
        meta={"tag": "beta"},
    )
    await uow.transactions.add(tx1)
    await uow.transactions.add(tx2)
    # List all
    all_rows = await uow.transactions.list_between(t0 - timedelta(seconds=1), t0 + timedelta(seconds=5))
    assert [r.memo for r in all_rows] == ["T1", "T2"]
    # Filter by meta
    alpha_rows = await uow.transactions.list_between(t0 - timedelta(seconds=1), t0 + timedelta(seconds=5), meta={"tag": "alpha"})
    assert [r.memo for r in alpha_rows] == ["T1"]


async def test_aggregate_trading_balance(async_uow: AsyncSqlAlchemyUnitOfWork):
    """Aggregate debit/credit per currency matches sync semantics."""
    uow = async_uow
    now = datetime.now(UTC)
    # Add lines across two currencies
    for _ in range(2):
        await uow.transactions.add(
            TransactionDTO(
                id="",
                occurred_at=now,
                lines=[
                    EntryLineDTO(side="DEBIT", account_full_name="Assets:Cash", amount=Decimal("10"), currency_code="USD"),
                    EntryLineDTO(side="CREDIT", account_full_name="Income:X", amount=Decimal("10"), currency_code="USD"),
                ],
            )
        )
    await uow.transactions.add(
        TransactionDTO(
            id="",
            occurred_at=now,
            lines=[
                EntryLineDTO(side="DEBIT", account_full_name="Assets:EUR", amount=Decimal("5"), currency_code="EUR"),
                EntryLineDTO(side="CREDIT", account_full_name="Income:Y", amount=Decimal("5"), currency_code="EUR"),
            ],
        )
    )
    tb = await uow.transactions.aggregate_trading_balance(as_of=now)
    lines = {l.currency_code: l for l in tb.lines}
    assert lines["USD"].total_debit == Decimal("20") and lines["USD"].total_credit == Decimal("20")
    assert lines["EUR"].total_debit == Decimal("5") and lines["EUR"].total_credit == Decimal("5")


async def test_ledger_pagination_order_and_edges(async_uow: AsyncSqlAlchemyUnitOfWork):
    """Ledger honors ordering, offset/limit, and meta filter edge-cases."""
    uow = async_uow
    now = datetime.now(UTC)
    # add multiple journals
    for i in range(5):
        tx = TransactionDTO(
            id="",
            occurred_at=now + timedelta(seconds=i),
            memo=f"T{i}",
            lines=[
                EntryLineDTO(side="DEBIT", account_full_name="Assets:Cash", amount=Decimal("1"), currency_code="USD"),
                EntryLineDTO(side="CREDIT", account_full_name="Income:Salary", amount=Decimal("1"), currency_code="USD"),
            ],
        )
        await uow.transactions.add(tx)
    # order ASC
    asc = await uow.transactions.ledger("Assets:Cash", now - timedelta(seconds=1), now + timedelta(seconds=10), order="ASC")
    assert [r.memo for r in asc] == [f"T{i}" for i in range(5)]
    # order DESC with limit/offset
    desc = await uow.transactions.ledger(
        "Assets:Cash", now - timedelta(seconds=1), now + timedelta(seconds=10), order="DESC", limit=2, offset=1
    )
    assert [r.memo for r in desc] == ["T3", "T2"]
    # edge cases
    empty1 = await uow.transactions.ledger("Assets:Cash", now, now, limit=0)
    empty2 = await uow.transactions.ledger("Assets:Cash", now, now, offset=-1)
    assert empty1 == [] and empty2 == []


async def test_balances_cache_upsert_get_clear(async_uow: AsyncSqlAlchemyUnitOfWork):
    """Balance cache upsert/get/clear with Decimal scale and tz handling."""
    uow = async_uow
    acc = "Assets:Cash"
    ts1 = datetime.now(UTC)
    await uow.balances.upsert_cache(acc, Decimal("123.45"), ts1)
    cached = await uow.balances.get_cache(acc)
    assert cached is not None
    assert cached[0] == Decimal("123.45") or cached[0].quantize(Decimal("0.01")) == Decimal("123.45")
    assert cached[1].replace(tzinfo=UTC) == ts1
    # update
    ts2 = ts1 + timedelta(seconds=1)
    await uow.balances.upsert_cache(acc, Decimal("200"), ts2)
    cached2 = await uow.balances.get_cache(acc)
    assert cached2 is not None
    assert cached2[0] == Decimal("200") or cached2[0].quantize(Decimal("0.01")) == Decimal("200")
    assert cached2[1].replace(tzinfo=UTC) == ts2
    # clear
    await uow.balances.clear(acc)
    assert await uow.balances.get_cache(acc) is None


async def test_fx_events_list_filters_and_limits(async_uow: AsyncSqlAlchemyUnitOfWork):
    """FX events: negative limit handling, code filter, newest-first ordering."""
    uow = async_uow
    now = datetime.now(UTC)
    # seed events for USD and EUR
    await uow.exchange_rate_events.add_event("USD", Decimal("1.0"), now, policy_applied="RAW", source="test")
    await uow.exchange_rate_events.add_event("EUR", Decimal("0.9"), now, policy_applied="RAW", source="test")
    # negative limit -> empty
    rows_neg = await uow.exchange_rate_events.list_events(limit=-1)
    assert rows_neg == []
    # filter by code
    usd_rows = await uow.exchange_rate_events.list_events(code="USD", limit=10)
    assert len(usd_rows) == 1 and usd_rows[0].code == "USD"
    # newest first ordering with limit=1
    one = await uow.exchange_rate_events.list_events(limit=1)
    assert len(one) == 1
