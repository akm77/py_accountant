from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from application.dto.models import EntryLineDTO
from application.use_cases_async import (
    AsyncCreateAccount,
    AsyncCreateCurrency,
    AsyncGetAccount,
    AsyncGetAccountBalance,
    AsyncGetLedger,
    AsyncGetTradingBalance,
    AsyncListAccounts,
    AsyncListCurrencies,
    AsyncListTransactionsBetween,
    AsyncPostTransaction,
    AsyncSetBaseCurrency,
)
from domain.errors import ValidationError


class _TestClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


@pytest.mark.xfail(reason="REWRITE-DOMAIN (I13): balance/trading use cases rely on repo methods removed in I13", strict=False)
async def test_async_use_cases_smoke(async_uow):  # type: ignore[missing-type-doc]
    clock = _TestClock()

    # Create currencies
    create_cur = AsyncCreateCurrency(async_uow)
    usd = await create_cur("USD")
    eur = await create_cur("EUR", exchange_rate=Decimal("0.9"))
    # Set base currency
    set_base = AsyncSetBaseCurrency(async_uow)
    await set_base("USD")
    # List currencies
    lst_cur = AsyncListCurrencies(async_uow)
    all_cur = await lst_cur()
    assert {c.code for c in all_cur} >= {"USD", "EUR"}
    base = [c for c in all_cur if c.is_base]
    assert len(base) == 1 and base[0].code == "USD"

    # Create account
    create_acc = AsyncCreateAccount(async_uow)
    cash_acc = await create_acc("Assets:Cash", "USD")
    assert cash_acc.full_name == "Assets:Cash"

    # Post transaction (DEBIT 100 USD, CREDIT 100 USD self-balancing)
    post_tx = AsyncPostTransaction(async_uow, clock)
    lines = [
        EntryLineDTO(side="DEBIT", account_full_name="Assets:Cash", amount=Decimal("100"), currency_code="USD"),
        EntryLineDTO(side="CREDIT", account_full_name="Assets:Cash", amount=Decimal("100"), currency_code="USD"),
    ]
    tx = await post_tx(lines, memo="init")
    assert tx.id.startswith("tx:")

    # List between window
    list_between = AsyncListTransactionsBetween(async_uow)
    window = await list_between(clock.now() - timedelta(days=1), clock.now() + timedelta(days=1))
    assert window, "Expected at least one transaction in window"

    # Ledger (limit=0 -> empty, offset<0 -> empty)
    get_ledger = AsyncGetLedger(async_uow, clock)
    empty_limit = await get_ledger("Assets:Cash", limit=0)
    assert empty_limit == []
    empty_offset = await get_ledger("Assets:Cash", offset=-5)
    assert empty_offset == []
    asc_ledger = await get_ledger("Assets:Cash", order="ASC")
    desc_ledger = await get_ledger("Assets:Cash", order="DESC")
    assert asc_ledger and desc_ledger

    # Account balance
    get_balance = AsyncGetAccountBalance(async_uow, clock)
    bal = await get_balance("Assets:Cash")
    assert isinstance(bal, Decimal)

    # Trading balance
    get_trading = AsyncGetTradingBalance(async_uow, clock)
    tb = await get_trading()
    assert tb.lines

    # Get account / list accounts
    get_acc = AsyncGetAccount(async_uow)
    fetched = await get_acc("Assets:Cash")
    assert fetched and fetched.id == cash_acc.id
    list_acc = AsyncListAccounts(async_uow)
    all_acc = await list_acc()
    assert any(a.full_name == "Assets:Cash" for a in all_acc)


@pytest.mark.asyncio
async def test_async_set_base_missing_currency_raises(async_uow):
    set_base = AsyncSetBaseCurrency(async_uow)
    with pytest.raises((ValidationError, ValueError)):
        await set_base("NOPE")


@pytest.mark.asyncio
async def test_async_create_account_missing_currency(async_uow):
    create_acc = AsyncCreateAccount(async_uow)
    with pytest.raises(ValueError):
        await create_acc("Assets:Cash", "NOPE")


@pytest.mark.asyncio
async def test_async_post_transaction_missing_account(async_uow):
    from decimal import Decimal

    create_cur = AsyncCreateCurrency(async_uow)
    await create_cur("USD")
    post_tx = AsyncPostTransaction(async_uow, _TestClock())
    lines = [EntryLineDTO(side="DEBIT", account_full_name="Assets:Cash", amount=Decimal("5"), currency_code="USD")]
    with pytest.raises(ValueError):
        await post_tx(lines)
