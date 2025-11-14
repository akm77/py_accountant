from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

from application.dto.models import (
    EntryLineDTO,
    RichTransactionDTO,
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
    - Fallback: if transactions.account_balance is DEPRECATED (NotImplementedError),
      compute balance manually by scanning ledger entries up to ``as_of``.
    """
    uow: AsyncUnitOfWork
    clock: Clock

    async def __call__(self, account_full_name: str, as_of: datetime | None = None) -> Decimal:
        """Return computed account balance at ``as_of`` (or now).

        Fallback logic handles repositories where account_balance was removed in I13
        (CRUD-only). Manual computation sums DEBIT amounts minus CREDIT amounts
        for matching account ledger lines.
        """
        ts = as_of or self.clock.now()
        try:
            return await self.uow.transactions.account_balance(account_full_name, ts)
        except NotImplementedError:
            from decimal import Decimal
            # Manual ledger scan from epoch to ts
            start = datetime.fromtimestamp(0, tz=ts.tzinfo)
            entries = await self.uow.transactions.ledger(account_full_name, start, ts, None, offset=0, limit=None, order="ASC")
            total = Decimal("0")
            for tx in entries:
                for line in tx.lines:
                    if line.account_full_name != account_full_name:
                        continue
                    side = line.side if isinstance(line.side, str) else str(line.side.value)
                    if side.upper() == "DEBIT":
                        total += line.amount
                    elif side.upper() == "CREDIT":
                        total -= line.amount
            return total

