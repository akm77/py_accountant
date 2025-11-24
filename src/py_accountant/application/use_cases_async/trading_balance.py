from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from py_accountant.application.dto.models import (
    TradingBalanceLineDetailed,
    TradingBalanceLineSimple,
)
from py_accountant.application.ports import AsyncUnitOfWork, Clock
from py_accountant.domain.currencies import Currency
from py_accountant.domain.errors import ValidationError
from py_accountant.domain.ledger import LedgerEntry
from py_accountant.domain.trading_balance import ConvertedAggregator, RawAggregator


def _epoch_with_tz(now: datetime) -> datetime:
    """Return Unix epoch (0) with the timezone of ``now``.

    Helper kept local to avoid cross-module coupling; ensures start default
    retains tz-awareness consistent with repository queries.
    """
    return datetime.fromtimestamp(0, tz=now.tzinfo)


@dataclass(slots=True)
class AsyncGetTradingBalanceRaw:
    """Compute raw (non-converted) trading balance within a time window.

    Aggregates debit/credit per currency using domain ``RawAggregator`` and
    returns a list of ``TradingBalanceLineSimple`` sorted by currency code.

    Error semantics:
    - ValueError: invalid window parameters (start > end) or invalid meta type.
    - ValidationError: propagated from domain LedgerEntry construction (side, amount>0, currency code length).
    - DomainError: not used for raw aggregation (no balance invariant at report level).

    Repository usage remains CRUD-only (``transactions.list_between``).
    """

    uow: AsyncUnitOfWork
    clock: Clock

    async def __call__(
        self,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        meta: dict[str, Any] | None = None,
    ) -> list[TradingBalanceLineSimple]:
        """Return raw trading balance lines (possibly empty).

        Args:
            start: Inclusive window start (defaults epoch with tz of ``clock.now()``).
            end: Inclusive window end (defaults ``clock.now()``).
            meta: Optional dict for exact-match metadata filtering.

        Returns:
            List of ``TradingBalanceLineSimple``; empty if no transactions/lines.
        """
        now = self.clock.now()
        start_dt = start or _epoch_with_tz(now)
        end_dt = end or now
        if start_dt > end_dt:
            raise ValueError("start > end")
        if meta is not None and not isinstance(meta, dict):
            raise ValueError("meta must be a dict or None")

        txs = await self.uow.transactions.list_between(start_dt, end_dt, meta)
        entries: list[LedgerEntry] = []
        for tx in txs:
            for line in tx.lines:
                try:
                    entries.append(
                        LedgerEntry(side=line.side, amount=line.amount, currency_code=line.currency_code)
                    )
                except ValidationError as ve:
                    # Re-propagate domain validation errors unchanged
                    raise ve
        if not entries:
            return []
        raw_lines = RawAggregator().aggregate(entries)
        return [
            TradingBalanceLineSimple(
                currency_code=line.currency_code,
                debit=line.debit,
                credit=line.credit,
                net=line.net,
            )
            for line in raw_lines
        ]


@dataclass(slots=True)
class AsyncGetTradingBalanceDetailed:
    """Compute detailed trading balance with conversion to a base currency.

    Uses domain ``ConvertedAggregator`` to aggregate and convert raw per-currency
    totals to base currency amounts. Base currency may be inferred if
    ``base_currency`` argument is omitted (detected via domain helper on loaded
    currencies). Public result lines are ``TradingBalanceLineDetailed`` sorted by currency code.

    Error semantics:
    - ValueError: invalid window (start > end) or meta type not dict/None.
    - ValidationError: domain validation issues (invalid ledger entry, missing base, unknown currency,
      missing/non-positive rate for non-base currency).
    - DomainError: not raised here (no balancing invariant enforced at report level).
    """

    uow: AsyncUnitOfWork
    clock: Clock

    async def __call__(
        self,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        meta: dict[str, Any] | None = None,
        base_currency: str | None = None,
    ) -> list[TradingBalanceLineDetailed]:
        """Return detailed trading balance lines (possibly empty).

        Args:
            start: Inclusive window start (defaults epoch with tz of ``clock.now()``).
            end: Inclusive window end (defaults ``clock.now()``).
            meta: Optional dict for metadata filtering (exact match on all key/value pairs).
            base_currency: Explicit base currency code; if None, inferred from repository currencies.

        Returns:
            List of ``TradingBalanceLineDetailed``; empty if no transactions.
        """
        now = self.clock.now()
        start_dt = start or _epoch_with_tz(now)
        end_dt = end or now
        if start_dt > end_dt:
            raise ValueError("start > end")
        if meta is not None and not isinstance(meta, dict):
            raise ValueError("meta must be a dict or None")

        txs = await self.uow.transactions.list_between(start_dt, end_dt, meta)
        entries: list[LedgerEntry] = []
        for tx in txs:
            for line in tx.lines:
                try:
                    entries.append(
                        LedgerEntry(side=line.side, amount=line.amount, currency_code=line.currency_code)
                    )
                except ValidationError as ve:
                    raise ve

        # Load currencies (CRUD-only) and project to domain Currency objects (needed even if no entries to validate base presence)
        cur_dtos = await self.uow.currencies.list_all()
        domain_currencies: list[Currency] = []
        for dto in cur_dtos:
            try:
                domain_currencies.append(
                    Currency(code=dto.code, is_base=dto.is_base, rate_to_base=dto.exchange_rate)
                )
            except ValidationError as ve:
                raise ve

        # Validate / determine base currency early (even when no entries) per spec
        if base_currency is not None:
            base_norm = base_currency.strip().upper() if base_currency else ""
            if not any(c.code == base_norm for c in domain_currencies):
                raise ValidationError(f"Base currency not found: {base_currency!r}")
            base_code_final = base_norm
        else:
            # Infer
            from py_accountant.domain.currencies import get_base_currency as _gbc

            base_obj = _gbc(domain_currencies)
            if base_obj is None:
                raise ValidationError("Base currency is not defined")
            base_code_final = base_obj.code

        if not entries:
            return []

        converted = ConvertedAggregator().aggregate(entries, domain_currencies, base_code=base_code_final)
        return [
            TradingBalanceLineDetailed(
                currency_code=line.currency_code,
                base_currency_code=line.base_currency_code,
                debit=line.debit,
                credit=line.credit,
                net=line.net,
                used_rate=line.used_rate,
                debit_base=line.debit_base,
                credit_base=line.credit_base,
                net_base=line.net_base,
            )
            for line in converted
        ]
