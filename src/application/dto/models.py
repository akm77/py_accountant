from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any


@dataclass(slots=True)
class CurrencyDTO:
    code: str
    name: str | None = None
    precision: int = 2
    exchange_rate: Decimal | None = None  # latest known rate vs base (None if base or unknown)
    is_base: bool = False  # explicit base currency flag (singleton)


@dataclass(slots=True)
class AccountDTO:
    id: str
    name: str
    full_name: str
    currency_code: str
    parent_id: str | None = None


@dataclass(slots=True)
class EntryLineDTO:
    side: str  # 'DEBIT' or 'CREDIT'
    account_full_name: str
    amount: Decimal
    currency_code: str
    exchange_rate: Decimal | None = None  # if None, will be auto-populated
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class TransactionDTO:
    id: str
    occurred_at: datetime
    lines: list[EntryLineDTO]
    memo: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class TradingBalanceLineDTO:
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
    as_of: datetime
    lines: list[TradingBalanceLineDTO]
    base_currency: str | None = None
    base_total: Decimal | None = None


@dataclass(slots=True)
class RichTransactionDTO:
    id: str
    occurred_at: datetime
    memo: str | None
    lines: list[EntryLineDTO]
    meta: dict[str, Any]


# Helper input for batch rate updates
@dataclass(slots=True)
class RateUpdateInput:
    code: str
    rate: Decimal
