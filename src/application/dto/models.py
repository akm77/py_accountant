from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any

# Explicit public export surface for DTOs
__all__ = [
    "CurrencyDTO",
    "AccountDTO",
    "EntryLineDTO",
    "TransactionDTO",
    "TradingBalanceLineDTO",
    "TradingBalanceDTO",
    "RichTransactionDTO",
    "RateUpdateInput",
    "ExchangeRateEventDTO",
    # New DTOs introduced in I09
    "TradingBalanceLineSimple",
    "TradingBalanceLineDetailed",
]


@dataclass(slots=True)
class CurrencyDTO:
    """Currency settings DTO: code, optional name, precision and last known rate.

    No I/O or side effects; used to move data between layers.
    """

    code: str
    name: str | None = None
    precision: int = 2
    exchange_rate: Decimal | None = None  # latest known rate vs base (None if base or unknown)
    is_base: bool = False  # explicit base currency flag (singleton)


@dataclass(slots=True)
class AccountDTO:
    """Account reference DTO with hierarchical name and currency binding."""

    id: str
    name: str
    full_name: str
    currency_code: str
    parent_id: str | None = None


@dataclass(slots=True)
class EntryLineDTO:
    """Transaction line DTO describing one debit/credit entry in a specific currency."""

    side: str  # 'DEBIT' or 'CREDIT'
    account_full_name: str
    amount: Decimal
    currency_code: str
    exchange_rate: Decimal | None = None  # if None, will be auto-populated
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class TransactionDTO:
    """Transaction DTO carrying timestamped memo and a list of entry lines."""

    id: str
    occurred_at: datetime
    lines: list[EntryLineDTO]
    memo: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)


# NOTE: Legacy mixed trading balance line kept for compatibility with existing tests.
# It may be removed or aliased in a later iteration (I10) once migration is complete.
@dataclass(slots=True)
class TradingBalanceLineDTO:
    """Legacy mixed trading balance line with optional conversion fields (deprecated)."""

    currency_code: str
    total_debit: Decimal
    total_credit: Decimal
    balance: Decimal
    # New converted fields (optional; populated when base conversion applied)
    converted_debit: Decimal | None = None
    converted_credit: Decimal | None = None
    converted_balance: Decimal | None = None
    # New transparency fields for detailed conversion
    rate_used: Decimal | None = None
    rate_fallback: bool = False


@dataclass(slots=True)
class TradingBalanceDTO:
    """Aggregated trading balance as of a timestamp with optional base totals."""

    as_of: datetime
    lines: list[TradingBalanceLineDTO]
    base_currency: str | None = None
    base_total: Decimal | None = None


@dataclass(slots=True)
class RichTransactionDTO:
    """Convenience DTO combining transaction core fields and typed lines/meta."""

    id: str
    occurred_at: datetime
    memo: str | None
    lines: list[EntryLineDTO]
    meta: dict[str, Any]


# Helper input for batch rate updates
@dataclass(slots=True)
class RateUpdateInput:
    """Simple input record for bulk currency rate updates."""

    code: str
    rate: Decimal


@dataclass(slots=True)
class ExchangeRateEventDTO:
    """Event record returned by exchange-rate services/persistence."""

    id: int | None
    code: str
    rate: Decimal
    occurred_at: datetime
    policy_applied: str
    source: str | None = None


# I09: Split trading balance DTO into simple and detailed types.
@dataclass(slots=True, frozen=True)
class TradingBalanceLineSimple:
    """Simple trading-balance line: raw amounts per currency without conversion fields.

    Contains only currency_code and raw debit/credit/net values.
    """

    currency_code: str
    debit: Decimal
    credit: Decimal
    net: Decimal


@dataclass(slots=True, frozen=True)
class TradingBalanceLineDetailed:
    """Detailed trading-balance line: raw values plus conversion to base currency.

    used_rate is normalized in domain to 6-decimal precision. Base amounts are in
    base_currency_code and reflect the applied used_rate.
    """

    currency_code: str
    base_currency_code: str
    debit: Decimal
    credit: Decimal
    net: Decimal
    used_rate: Decimal
    debit_base: Decimal
    credit_base: Decimal
    net_base: Decimal

