from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

from application.dto.models import (
    EntryLineDTO,
    RichTransactionDTO,
    TradingBalanceDTO,
    TransactionDTO,
)
from application.interfaces.ports import AsyncUnitOfWork, Clock
from domain.errors import ValidationError
from domain.ledger import LedgerEntry, LedgerValidator


@dataclass(slots=True)
class AsyncPostTransaction:
    """Persist a financial transaction after domain ledger balance validation.

    Contract:
      AsyncPostTransaction(uow, clock)(lines: list[EntryLineDTO], memo: str|None, meta: dict|None) -> TransactionDTO

    Steps:
      1. Guard empty list (ValidationError).
      2. For each provided line: ensure account exists (ValueError) and currency exists (ValueError).
      3. Project lines to domain LedgerEntry (side/amount/currency_code validation -> ValidationError).
      4. Load all distinct currencies referenced by lines from repository (ValueError if any missing).
      5. Project currency DTOs to domain Currency value objects (ValidationError on invalid code/rate).
      6. Run LedgerValidator.validate(entries, currencies_domain) — performs:
         - Base currency detection (ValidationError if absent).
         - Unknown currency among entries (ValidationError).
         - Missing/non‑positive rate_to_base for non‑base currency (ValidationError).
         - Debit/Credit imbalance after conversion & money quantize (DomainError).
      7. Persist TransactionDTO (id = "tx:<uuidhex>") with occurred_at = clock.now().

    Error classification:
      - ValidationError: empty lines, invalid side, non‑positive amount, bad currency code length, absent base currency,
        unknown currency during domain validation, missing/non‑positive rate_to_base for non‑base currency.
      - DomainError: ledger not balanced after conversion and quantization.
      - ValueError: missing external resources (account or currency DTO not found before domain validation).

    Side effects: inserts journal + transaction lines via async repository.

    Notes:
      - Does not mutate exchange rates or perform balance caching.
      - Repositories remain CRUD‑only; all formal business validation lives in domain objects.
    """
    uow: AsyncUnitOfWork
    clock: Clock

    async def __call__(
        self,
        lines: list[EntryLineDTO],
        memo: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> TransactionDTO:
        """Validate input & domain ledger balance, then persist and return TransactionDTO.

        Raises:
          ValidationError | DomainError | ValueError per class docstring.
        """
        # 1. Empty list guard (domain formatting error)
        if not lines:
            raise ValidationError("No lines provided")

        # 2. Resource existence checks (accounts + currencies)
        for line in lines:
            acc = await self.uow.accounts.get_by_full_name(line.account_full_name)
            if not acc:
                raise ValueError(f"Account not found: {line.account_full_name}")
            cur_dto = await self.uow.currencies.get_by_code(line.currency_code.upper())
            if not cur_dto:
                raise ValueError(f"Currency not found: {line.currency_code}")

        # 3. Project to domain ledger entries (formal field validation)
        entries: list[LedgerEntry] = []
        for line in lines:
            # LedgerEntry performs side/amount/currency_code validation
            entries.append(LedgerEntry(side=line.side, amount=line.amount, currency_code=line.currency_code))

        # 4. Load all currencies (not just referenced) to ensure base detection works even when lines omit base
        all_cur_dtos = await self.uow.currencies.list_all()
        dto_map: dict[str, Any] = {d.code: d for d in all_cur_dtos}
        # Guard: ensure all referenced codes exist (classification ValueError)
        for code in {e.currency_code for e in entries}:
            if code not in dto_map:
                raise ValueError(f"Currency not found: {code}")
        # 5. Project DTOs to domain Currency objects
        from domain.currencies import Currency  # local import to keep async module surface concise
        currencies_domain: list[Currency] = []
        for dto in dto_map.values():
            currencies_domain.append(
                Currency(code=dto.code, is_base=dto.is_base, rate_to_base=dto.exchange_rate)
            )

        # 6. Domain ledger balance validation
        LedgerValidator.validate(entries, currencies_domain)

        # 7. Persist transaction
        tx = TransactionDTO(
            id=f"tx:{uuid4().hex}",
            occurred_at=self.clock.now(),
            lines=lines,
            memo=memo,
            meta=meta or {},
        )
        return await self.uow.transactions.add(tx)


@dataclass(slots=True)
class AsyncListTransactionsBetween:
    """Purpose:
    List transactions between start and end timestamps (inclusive boundaries).

    Parameters:
    - uow: AsyncUnitOfWork.
    - start: Start datetime (required).
    - end: End datetime (required).
    - meta: Optional meta filter; all key/value pairs must match exactly.

    Returns:
    - list[TransactionDTO]: ordered ascending by occurred_at.

    Raises:
    - ValueError: if ``start > end``.

    Notes:
    - ``meta`` of None or empty dict yields unfiltered results.
    """
    uow: AsyncUnitOfWork

    async def __call__(
        self,
        start: datetime,
        end: datetime,
        meta: dict[str, Any] | None = None,
    ) -> list[TransactionDTO]:
        """Return transactions in window; validate temporal ordering."""
        if start > end:
            raise ValueError("start > end")
        return await self.uow.transactions.list_between(start, end, meta)


@dataclass(slots=True)
class AsyncGetLedger:
    """Purpose:
    Return ledger entries for an account with pagination, ordering, and meta filtering.

    Parameters:
    - uow: AsyncUnitOfWork.
    - account_full_name: Full name of target account.
    - start: Optional start time (defaults epoch with same tz as now).
    - end: Optional end time (defaults now).
    - meta: Optional key/value filter dict.
    - offset: Pagination offset (>=0); negative returns empty list.
    - limit: Optional limit; <=0 returns empty list.
    - order: "ASC" or "DESC" ordering by occurred_at.

    Returns:
    - list[RichTransactionDTO].

    Raises:
    - ValueError: on invalid parameters (ordering, negatives).

    Notes:
    - Mirrors async repository semantics; minimal validation performed here.
    """
    uow: AsyncUnitOfWork
    clock: Clock

    async def __call__(
        self,
        account_full_name: str,
        start: datetime | None = None,
        end: datetime | None = None,
        meta: dict[str, Any] | None = None,
        *,
        offset: int = 0,
        limit: int | None = None,
        order: str = "ASC",
    ) -> list[RichTransactionDTO]:
        """Return ledger entries; apply basic validation and pagination rules."""
        if not account_full_name or ":" not in account_full_name:
            raise ValueError("Invalid account_full_name format")
        start_dt = start or datetime.fromtimestamp(0, tz=self.clock.now().tzinfo)
        end_dt = end or self.clock.now()
        if start_dt > end_dt:
            raise ValueError("start > end")
        if offset < 0:
            return []
        if limit is not None and limit <= 0:
            return []
        order_up = order.upper()
        if order_up not in {"ASC", "DESC"}:
            raise ValueError("order must be ASC or DESC")
        if meta is not None and not isinstance(meta, dict):
            raise ValueError("meta must be a dict or None")
        return await self.uow.transactions.ledger(
            account_full_name,
            start_dt,
            end_dt,
            meta,
            offset=offset,
            limit=limit,
            order=order_up,
        )


@dataclass(slots=True)
class AsyncGetAccountBalance:
    """Purpose:
    Compute balance for an account at a point in time.

    Parameters:
    - uow: AsyncUnitOfWork.
    - account_full_name: Account identifier.
    - as_of: Timestamp for balance evaluation (defaults to now).

    Returns:
    - Decimal balance.

    Raises:
    - None.

    Notes:
    - Repository currently ignores ``as_of`` detail due to simplified schema.
    """
    uow: AsyncUnitOfWork
    clock: Clock

    async def __call__(self, account_full_name: str, as_of: datetime | None = None) -> Decimal:
        """Return computed account balance at ``as_of`` (or now)."""
        ts = as_of or self.clock.now()
        return await self.uow.transactions.account_balance(account_full_name, ts)


@dataclass(slots=True)
class AsyncGetTradingBalance:
    """DEPRECATED (I18): use AsyncGetTradingBalanceRaw / AsyncGetTradingBalanceDetailed
    from application.use_cases_async.trading_balance instead of this legacy aggregator.

    Purpose:
    Aggregate trading balance (debit/credit per currency) and perform optional
    base currency conversion.

    Parameters:
    - uow: AsyncUnitOfWork.
    - clock: Clock.
    - as_of: Optional timestamp for aggregation reference (defaults now).
    - base_currency: Optional explicit base currency code; if omitted attempts
      to infer via repository ``get_base``.

    Returns:
    - TradingBalanceDTO with optional converted fields populated.

    Raises:
    - None.

    Notes:
    - Conversion uses stored ``exchange_rate`` where available; missing or base
      currency defaults to rate=1.
    """
    uow: AsyncUnitOfWork
    clock: Clock

    async def __call__(self, as_of: datetime | None = None, base_currency: str | None = None) -> TradingBalanceDTO:
        """Return trading balance with optional base currency conversion."""
        ref = as_of or self.clock.now()
        tb = await self.uow.transactions.aggregate_trading_balance(as_of=ref, base_currency=base_currency)
        inferred = base_currency
        if inferred is None:
            base_dto = await self.uow.currencies.get_base()
            if base_dto:
                inferred = base_dto.code
        if inferred:
            total = Decimal("0")
            for line in tb.lines:
                cur_obj = await self.uow.currencies.get_by_code(line.currency_code)
                rate = Decimal("1")
                if cur_obj and cur_obj.code != inferred and cur_obj.exchange_rate:
                    rate = cur_obj.exchange_rate
                zero = Decimal("0")
                line.converted_debit = line.total_debit / rate if rate != zero else line.total_debit
                line.converted_credit = line.total_credit / rate if rate != zero else line.total_credit
                line.converted_balance = line.balance / rate if rate != zero else line.balance
                # Ensure presentation-friendly rounding parity with legacy (money scale=2)
                from application.utils.quantize import money_quantize
                if line.converted_debit is not None:
                    line.converted_debit = money_quantize(line.converted_debit)
                if line.converted_credit is not None:
                    line.converted_credit = money_quantize(line.converted_credit)
                if line.converted_balance is not None:
                    line.converted_balance = money_quantize(line.converted_balance)
                total += line.converted_balance  # type: ignore[arg-type]
            # Quantize base_total too
            from application.utils.quantize import money_quantize as _mq
            tb.base_currency = inferred
            tb.base_total = _mq(total)
        return tb
