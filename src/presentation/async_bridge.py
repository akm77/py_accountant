from __future__ import annotations

import os
from datetime import datetime
from decimal import Decimal
from typing import Any

from application.dto.models import (
    AccountDTO,
    CurrencyDTO,
    EntryLineDTO,
    ExchangeRateEventDTO,
    RichTransactionDTO,
    TradingBalanceDTO,
    TransactionDTO,
)
from application.use_cases_async.accounts import (
    AsyncCreateAccount,
    AsyncGetAccount,
    AsyncListAccounts,
)
from application.use_cases_async.currencies import (
    AsyncCreateCurrency,
    AsyncListCurrencies,
    AsyncSetBaseCurrency,
)
from application.use_cases_async.fx_audit import (
    AsyncAddExchangeRateEvent,
    AsyncListExchangeRateEvents,
)
from application.use_cases_async.ledger import (
    AsyncGetAccountBalance,
    AsyncGetLedger,
    AsyncGetTradingBalance,
    AsyncListTransactionsBetween,
    AsyncPostTransaction,
)
from domain.value_objects import DomainError
from infrastructure.persistence.inmemory.clock import SystemClock
from infrastructure.persistence.sqlalchemy.models import Base  # type: ignore
from infrastructure.persistence.sqlalchemy.uow import AsyncSqlAlchemyUnitOfWork
from infrastructure.utils.asyncio_utils import run_sync

_A_UOWS: dict[str, AsyncSqlAlchemyUnitOfWork] = {}
_A_SCHEMA_INIT: set[int] = set()


def _uow_key(url: str | None) -> str:
    test_id = os.environ.get("PYTEST_CURRENT_TEST")
    base = url or "__mem__"
    return f"{base}:{test_id}" if test_id else base


async def _ensure_schema(uow: AsyncSqlAlchemyUnitOfWork) -> None:
    eng_id = id(uow.engine)
    if eng_id in _A_SCHEMA_INIT:
        return
    async with uow.engine.begin() as conn:  # type: ignore[attr-defined]
        await conn.run_sync(Base.metadata.create_all)
    _A_SCHEMA_INIT.add(eng_id)


def _get_async_uow(url: str | None) -> AsyncSqlAlchemyUnitOfWork:
    key = _uow_key(url)
    if key in _A_UOWS:
        return _A_UOWS[key]
    uow = AsyncSqlAlchemyUnitOfWork(url)
    _A_UOWS[key] = uow
    return uow


def _current_db_url() -> str | None:
    return os.environ.get("DATABASE_URL")


def create_currency_sync(code: str, exchange_rate: Decimal | None = None) -> CurrencyDTO:
    url = _current_db_url()

    async def _run() -> CurrencyDTO:
        uow = _get_async_uow(url)
        await _ensure_schema(uow)
        try:
            async with uow:
                uc = AsyncCreateCurrency(uow)
                return await uc(code, exchange_rate)
        except ValueError as ve:
            raise DomainError(str(ve)) from ve

    return run_sync(_run())


def set_base_currency_sync(code: str) -> CurrencyDTO:
    url = _current_db_url()

    async def _run() -> CurrencyDTO:
        uow = _get_async_uow(url)
        await _ensure_schema(uow)
        try:
            async with uow:
                await AsyncSetBaseCurrency(uow)(code)
            async with uow:
                base = await uow.currencies.get_base()
                if base is None:
                    raise ValueError("Base currency not set")
                return base
        except ValueError as ve:
            raise DomainError(str(ve)) from ve

    return run_sync(_run())


def list_currencies_sync() -> list[CurrencyDTO]:
    url = _current_db_url()

    async def _run() -> list[CurrencyDTO]:
        uow = _get_async_uow(url)
        await _ensure_schema(uow)
        async with uow:
            return await AsyncListCurrencies(uow)()

    return run_sync(_run())


def create_account_sync(full_name: str, currency_code: str) -> AccountDTO:
    url = _current_db_url()

    async def _run() -> AccountDTO:
        uow = _get_async_uow(url)
        await _ensure_schema(uow)
        try:
            async with uow:
                return await AsyncCreateAccount(uow)(full_name, currency_code)
        except ValueError as ve:
            raise DomainError(str(ve)) from ve

    return run_sync(_run())


def get_account_sync(full_name: str) -> AccountDTO | None:
    url = _current_db_url()

    async def _run() -> AccountDTO | None:
        uow = _get_async_uow(url)
        await _ensure_schema(uow)
        async with uow:
            return await AsyncGetAccount(uow)(full_name)

    return run_sync(_run())


def list_accounts_sync() -> list[AccountDTO]:
    url = _current_db_url()

    async def _run() -> list[AccountDTO]:
        uow = _get_async_uow(url)
        await _ensure_schema(uow)
        async with uow:
            return await AsyncListAccounts(uow)()

    return run_sync(_run())


def get_currency_sync(code: str) -> CurrencyDTO | None:
    """Fetch currency by code from async repository, or None if not found."""
    url = _current_db_url()

    async def _run() -> CurrencyDTO | None:
        uow = _get_async_uow(url)
        await _ensure_schema(uow)
        async with uow:
            return await uow.currencies.get_by_code(code)

    return run_sync(_run())


def set_currency_rate_sync(code: str, new_rate: Decimal, *, policy_applied: str, source: str) -> CurrencyDTO:
    """Set exchange rate for an existing currency and append audit event.

    Returns updated CurrencyDTO. Raises DomainError if currency missing.
    """
    url = _current_db_url()
    clock = SystemClock()

    async def _run() -> CurrencyDTO:
        uow = _get_async_uow(url)
        await _ensure_schema(uow)
        async with uow:
            cur = await uow.currencies.get_by_code(code)
            if not cur:
                raise DomainError(f"Currency not found: {code}")
            cur.exchange_rate = new_rate
            saved = await uow.currencies.upsert(cur)
            try:
                events_repo = getattr(uow, "exchange_rate_events", None)
                if events_repo:
                    await events_repo.add_event(code, new_rate, clock.now(), policy_applied, source)
            except Exception:
                # non-fatal
                pass
            await uow.commit()
            return saved

    return run_sync(_run())


def bulk_upsert_rates_sync(updates: list[tuple[str, Decimal]], *, policy_applied: str, source: str) -> int:
    """Bulk update exchange rates and append audit events for each entry.

    Returns number of updated currencies.
    """
    if not updates:
        return 0
    url = _current_db_url()
    clock = SystemClock()

    async def _run() -> int:
        uow = _get_async_uow(url)
        await _ensure_schema(uow)
        async with uow:
            await uow.currencies.bulk_upsert_rates(updates)
            try:
                events_repo = getattr(uow, "exchange_rate_events", None)
                if events_repo:
                    for code, r in updates:
                        await events_repo.add_event(code, r, clock.now(), policy_applied, source)
            except Exception:
                pass
            await uow.commit()
            return len(updates)

    return run_sync(_run())


# Amend post_transaction_sync to enforce balance validation similar to legacy behavior
def post_transaction_sync(
    lines: list[EntryLineDTO],
    memo: str | None = None,
    meta: dict[str, Any] | None = None,
) -> TransactionDTO:
    if not lines:
        raise DomainError("No lines provided")
    url = _current_db_url()
    clock = SystemClock()

    async def _is_balanced(uow: AsyncSqlAlchemyUnitOfWork, ls: list[EntryLineDTO]) -> bool:
        cur_set = {ln.currency_code for ln in ls}
        # Single-currency quick path
        if len(cur_set) == 1:
            total = Decimal("0")
            for ln in ls:
                total += ln.amount if ln.side.upper() == "DEBIT" else -ln.amount
            return total == Decimal("0")
        # Multi-currency: use base currency if configured; otherwise pivot to first line using provided rates
        base = await uow.currencies.get_base()
        pivot_code = base.code if base else ls[0].currency_code
        total_norm = Decimal("0")
        for ln in ls:
            amt = ln.amount
            sign = Decimal("1") if ln.side.upper() == "DEBIT" else Decimal("-1")
            if ln.currency_code == pivot_code:
                conv = amt
            else:
                rate = ln.exchange_rate
                if rate is None:
                    cur_dto = await uow.currencies.get_by_code(ln.currency_code)
                    rate = cur_dto.exchange_rate if cur_dto and cur_dto.exchange_rate is not None else Decimal("1")
                if rate == 0:
                    # Avoid division by zero; treat as no conversion available -> fail validation conservatively
                    return False
                conv = amt / rate
            total_norm += sign * conv
        return total_norm == Decimal("0")

    async def _run() -> TransactionDTO:
        uow = _get_async_uow(url)
        await _ensure_schema(uow)
        try:
            async with uow:
                # Validate balance prior to persisting for CLI parity
                ok = await _is_balanced(uow, lines)
                if not ok:
                    raise DomainError("Unbalanced transaction")
                return await AsyncPostTransaction(uow, clock)(lines, memo=memo, meta=meta)
        except ValueError as ve:
            raise DomainError(str(ve)) from ve

    return run_sync(_run())


def list_transactions_between_sync(
    start: datetime,
    end: datetime,
    meta: dict[str, Any] | None = None,
) -> list[TransactionDTO]:
    url = _current_db_url()

    async def _run() -> list[TransactionDTO]:
        uow = _get_async_uow(url)
        await _ensure_schema(uow)
        try:
            async with uow:
                return await AsyncListTransactionsBetween(uow)(start, end, meta)
        except ValueError as ve:
            raise DomainError(str(ve)) from ve

    return run_sync(_run())


def get_ledger_sync(
    account_full_name: str,
    start: datetime | None,
    end: datetime | None,
    meta: dict[str, Any] | None,
    offset: int = 0,
    limit: int | None = None,
    order: str = "ASC",
) -> list[RichTransactionDTO]:
    url = _current_db_url()
    clock = SystemClock()

    async def _run() -> list[RichTransactionDTO]:
        uow = _get_async_uow(url)
        await _ensure_schema(uow)
        try:
            async with uow:
                return await AsyncGetLedger(uow, clock)(
                    account_full_name,
                    start=start,
                    end=end,
                    meta=meta,
                    offset=offset,
                    limit=limit,
                    order=order,
                )
        except ValueError as ve:
            raise DomainError(str(ve)) from ve

    return run_sync(_run())


def get_account_balance_sync(account_full_name: str, as_of: datetime | None = None) -> Decimal:
    url = _current_db_url()
    clock = SystemClock()

    async def _run() -> Decimal:
        uow = _get_async_uow(url)
        await _ensure_schema(uow)
        async with uow:
            return await AsyncGetAccountBalance(uow, clock)(account_full_name, as_of=as_of)

    return run_sync(_run())


def get_trading_balance_sync(
    as_of: datetime | None = None,
    base_currency: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
) -> TradingBalanceDTO:
    url = _current_db_url()
    clock = SystemClock()

    async def _run() -> TradingBalanceDTO:
        uow = _get_async_uow(url)
        await _ensure_schema(uow)
        async with uow:
            return await AsyncGetTradingBalance(uow, clock)(as_of=as_of, base_currency=base_currency)

    return run_sync(_run())


def get_trading_balance_detailed_sync(
    base_currency: str | None,
    as_of: datetime | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
) -> TradingBalanceDTO:
    url = _current_db_url()
    clock = SystemClock()

    async def _run() -> TradingBalanceDTO:
        if not base_currency:
            raise DomainError("base_currency is required for detailed trading balance")
        uow = _get_async_uow(url)
        await _ensure_schema(uow)
        async with uow:
            tb = await AsyncGetTradingBalance(uow, clock)(as_of=as_of, base_currency=base_currency)
            # enrich transparency fields (rate_used, rate_fallback) already part of DTO lines
            for line in tb.lines:
                cur_obj = await uow.currencies.get_by_code(line.currency_code)
                if cur_obj and cur_obj.code != base_currency and cur_obj.exchange_rate:
                    rate = cur_obj.exchange_rate
                    fallback = False
                else:
                    rate = Decimal("1")
                    fallback = not (cur_obj and cur_obj.code == base_currency)
                zero = Decimal("0")
                line.converted_debit = line.total_debit / rate if rate != zero else line.total_debit
                line.converted_credit = line.total_credit / rate if rate != zero else line.total_credit
                line.converted_balance = line.balance / rate if rate != zero else line.balance
                line.rate_used = rate
                line.rate_fallback = fallback
            # compute base_total
            total = Decimal("0")
            for line in tb.lines:
                if line.converted_balance is not None:
                    total += line.converted_balance
            tb.base_currency = base_currency
            tb.base_total = total
            return tb

    return run_sync(_run())


def add_exchange_rate_event_sync(
    code: str,
    rate: Decimal,
    occurred_at: datetime,
    policy_applied: str,
    source: str | None,
) -> ExchangeRateEventDTO:
    url = _current_db_url()

    async def _run() -> ExchangeRateEventDTO:
        uow = _get_async_uow(url)
        await _ensure_schema(uow)
        async with uow:
            return await AsyncAddExchangeRateEvent(uow)(code, rate, occurred_at, policy_applied, source)

    return run_sync(_run())


def list_exchange_rate_events_sync(code: str | None = None, limit: int | None = None) -> list[ExchangeRateEventDTO]:
    url = _current_db_url()

    async def _run() -> list[ExchangeRateEventDTO]:
        uow = _get_async_uow(url)
        await _ensure_schema(uow)
        async with uow:
            return await AsyncListExchangeRateEvents(uow)(code, limit)

    return run_sync(_run())
