from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from application.dto.models import EntryLineDTO
from application.use_cases_async import (
    AsyncCreateAccount,
    AsyncCreateCurrency,
    AsyncGetTradingBalanceDetailed,
    AsyncGetTradingBalanceRaw,
    AsyncPostTransaction,
    AsyncSetBaseCurrency,
)
from domain.errors import ValidationError


class _Clock:
    def __init__(self, now_dt: datetime | None = None) -> None:
        self._now = now_dt or datetime.now(UTC)

    def now(self) -> datetime:  # minimal Clock impl
        return self._now


@pytest.mark.asyncio
async def test_trading_balance_raw_empty_returns_empty(async_uow):
    clock = _Clock()
    raw = AsyncGetTradingBalanceRaw(async_uow, clock)
    lines = await raw()
    assert lines == []


@pytest.mark.asyncio
async def test_trading_balance_raw_single_currency_aggregate(async_uow):
    clock = _Clock()
    # Seed USD base and account
    await AsyncCreateCurrency(async_uow)("USD")
    await AsyncSetBaseCurrency(async_uow)("USD")
    await AsyncCreateAccount(async_uow)("Assets:Cash", "USD")
    # Post balanced USD lines: DEBIT 10, CREDIT 10, then an extra DEBIT 3/CREDIT 0 to produce net 3? Instead keep balanced for validator and adjust expected totals.
    post = AsyncPostTransaction(async_uow, clock)
    await post([
        EntryLineDTO(side="DEBIT", account_full_name="Assets:Cash", amount=Decimal("10"), currency_code="USD"),
        EntryLineDTO(side="CREDIT", account_full_name="Assets:Cash", amount=Decimal("10"), currency_code="USD"),
    ])
    await post([
        EntryLineDTO(side="DEBIT", account_full_name="Assets:Cash", amount=Decimal("3"), currency_code="USD"),
        EntryLineDTO(side="CREDIT", account_full_name="Assets:Cash", amount=Decimal("3"), currency_code="USD"),
    ])
    raw = AsyncGetTradingBalanceRaw(async_uow, clock)
    lines = await raw()
    assert len(lines) == 1
    l = lines[0]
    assert l.currency_code == "USD"
    assert l.debit == Decimal("13.00")
    assert l.credit == Decimal("13.00")
    assert l.net == Decimal("0.00")


@pytest.mark.asyncio
async def test_trading_balance_raw_multi_currency_sorted_and_rounded(async_uow):
    clock = _Clock()
    await AsyncCreateCurrency(async_uow)("USD")
    await AsyncCreateCurrency(async_uow)("EUR", exchange_rate=Decimal("1.111111"))
    await AsyncSetBaseCurrency(async_uow)("USD")
    await AsyncCreateAccount(async_uow)("Assets:CashUSD", "USD")
    await AsyncCreateAccount(async_uow)("Assets:CashEUR", "EUR")
    post = AsyncPostTransaction(async_uow, clock)
    # USD balanced entries
    await post([
        EntryLineDTO(side="DEBIT", account_full_name="Assets:CashUSD", amount=Decimal("10.005"), currency_code="USD"),
        EntryLineDTO(side="CREDIT", account_full_name="Assets:CashUSD", amount=Decimal("10.005"), currency_code="USD"),
    ])
    # EUR balanced entries
    await post([
        EntryLineDTO(side="DEBIT", account_full_name="Assets:CashEUR", amount=Decimal("5.001"), currency_code="EUR"),
        EntryLineDTO(side="CREDIT", account_full_name="Assets:CashEUR", amount=Decimal("5.001"), currency_code="EUR"),
    ])
    raw = AsyncGetTradingBalanceRaw(async_uow, clock)
    lines = await raw()
    # Should be two currencies, sorted lexicographically: EUR, USD
    assert [l.currency_code for l in lines] == ["EUR", "USD"]
    eur = lines[0]
    usd = lines[1]
    assert eur.debit == Decimal("5.00") and eur.credit == Decimal("5.00") and eur.net == Decimal("0.00")
    assert usd.debit == Decimal("10.00") and usd.credit == Decimal("10.00") and usd.net == Decimal("0.00")


@pytest.mark.asyncio
async def test_trading_balance_detailed_base_detected_via_get_base(async_uow):
    # Base USD, EUR with rate
    clock = _Clock()
    await AsyncCreateCurrency(async_uow)("USD")
    await AsyncCreateCurrency(async_uow)("EUR", exchange_rate=Decimal("1.111111"))
    await AsyncSetBaseCurrency(async_uow)("USD")
    await AsyncCreateAccount(async_uow)("Assets:CashUSD", "USD")
    await AsyncCreateAccount(async_uow)("Assets:CashEUR", "EUR")
    post = AsyncPostTransaction(async_uow, clock)
    await post([
        EntryLineDTO(side="DEBIT", account_full_name="Assets:CashUSD", amount=Decimal("10"), currency_code="USD"),
        EntryLineDTO(side="CREDIT", account_full_name="Assets:CashUSD", amount=Decimal("10"), currency_code="USD"),
    ])
    await post([
        EntryLineDTO(side="DEBIT", account_full_name="Assets:CashEUR", amount=Decimal("5"), currency_code="EUR"),
        EntryLineDTO(side="CREDIT", account_full_name="Assets:CashEUR", amount=Decimal("5"), currency_code="EUR"),
    ])
    det = AsyncGetTradingBalanceDetailed(async_uow, clock)
    lines = await det()  # base inferred as USD
    assert [l.currency_code for l in lines] == ["EUR", "USD"]
    eur = lines[0]
    usd = lines[1]
    assert eur.base_currency_code == "USD"
    assert eur.used_rate == Decimal("1.111111")
    assert eur.debit_base == Decimal("5.56")
    assert eur.credit_base == Decimal("5.56")
    assert eur.net_base == Decimal("0.00")
    assert usd.used_rate == Decimal("1")
    assert usd.debit_base == usd.debit and usd.credit_base == usd.credit and usd.net_base == usd.net


@pytest.mark.asyncio
async def test_trading_balance_detailed_missing_base_raises_validation_error(async_uow):
    clock = _Clock()
    # Create currencies without setting base
    await AsyncCreateCurrency(async_uow)("USD")
    await AsyncCreateCurrency(async_uow)("EUR", exchange_rate=Decimal("1.1"))
    # No base selected; no need to post (detailed use case should fail during base inference)
    det = AsyncGetTradingBalanceDetailed(async_uow, clock)
    with pytest.raises(ValidationError):
        await det()


@pytest.mark.asyncio
async def test_trading_balance_detailed_nonbase_missing_rate_raises_validation_error(async_uow):
    clock = _Clock()
    await AsyncCreateCurrency(async_uow)("USD")
    await AsyncSetBaseCurrency(async_uow)("USD")
    await AsyncCreateCurrency(async_uow)("EUR")  # EUR without rate
    await AsyncCreateAccount(async_uow)("Assets:Cash", "USD")
    await AsyncCreateAccount(async_uow)("Assets:CashEUR", "EUR")
    post = AsyncPostTransaction(async_uow, clock)
    # Attempt to post EUR lines without rate triggers ValidationError via LedgerValidator
    with pytest.raises(ValidationError):
        await post([
            EntryLineDTO(side="DEBIT", account_full_name="Assets:CashEUR", amount=Decimal("5"), currency_code="EUR"),
            EntryLineDTO(side="CREDIT", account_full_name="Assets:CashEUR", amount=Decimal("5"), currency_code="EUR"),
        ])


@pytest.mark.asyncio
async def test_trading_balance_detailed_multi_currency_correct_conversion_and_used_rate_quantized(async_uow):
    clock = _Clock()
    await AsyncCreateCurrency(async_uow)("USD")
    await AsyncCreateCurrency(async_uow)("EUR", exchange_rate=Decimal("1.1111119"))
    await AsyncSetBaseCurrency(async_uow)("USD")
    await AsyncCreateAccount(async_uow)("Assets:CashUSD", "USD")
    await AsyncCreateAccount(async_uow)("Assets:CashEUR", "EUR")
    post = AsyncPostTransaction(async_uow, clock)
    await post([
        EntryLineDTO(side="DEBIT", account_full_name="Assets:CashUSD", amount=Decimal("10"), currency_code="USD"),
        EntryLineDTO(side="CREDIT", account_full_name="Assets:CashUSD", amount=Decimal("10"), currency_code="USD"),
    ])
    await post([
        EntryLineDTO(side="DEBIT", account_full_name="Assets:CashEUR", amount=Decimal("5"), currency_code="EUR"),
        EntryLineDTO(side="CREDIT", account_full_name="Assets:CashEUR", amount=Decimal("5"), currency_code="EUR"),
    ])
    det = AsyncGetTradingBalanceDetailed(async_uow, clock)
    lines = await det()
    eur = next(l for l in lines if l.currency_code == "EUR")
    # used_rate must be quantized to 6 dp
    assert eur.used_rate == Decimal("1.111112")


@pytest.mark.asyncio
async def test_window_validation_and_meta_type(async_uow):
    now = datetime.now(UTC)
    clock = _Clock(now)
    raw = AsyncGetTradingBalanceRaw(async_uow, clock)
    with pytest.raises(ValueError):
        await raw(start=now + timedelta(seconds=1), end=now)
    # Remove incorrect expectation: passing dict meta is valid; only wrong type should raise
    with pytest.raises(ValueError):
        await raw(meta=object())  # type: ignore[arg-type]
    det = AsyncGetTradingBalanceDetailed(async_uow, clock)
    with pytest.raises(ValueError):
        await det(start=now + timedelta(seconds=1), end=now)
    with pytest.raises(ValueError):
        await det(meta=object())  # type: ignore[arg-type]
