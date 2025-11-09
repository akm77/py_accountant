from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from enum import Enum

__all__ = [
    "DomainError",
    "CurrencyCode",
    "AccountName",
    "EntrySide",
    "ExchangeRate",
    "EntryLine",
    "TransactionVO",
]

from typing import Literal


class DomainError(ValueError):
    """Generic domain validation error."""


@dataclass(frozen=True, slots=True)
class CurrencyCode:
    code: str
    MAX_LEN: int = 10

    def __post_init__(self):  # type: ignore[override]
        code = self.code
        if not code or not isinstance(code, str):  # noqa: SIM103
            raise DomainError("Currency code must be non-empty string")
        if len(code) < 2 or len(code) > self.MAX_LEN:
            raise DomainError(f"Currency code length must be between 2 and {self.MAX_LEN}")
        if not code.isascii() or not code.replace("_", "").isalnum():
            raise DomainError("Currency code must be ASCII alnum + '_' only")
        object.__setattr__(self, "code", code.upper())

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.code


@dataclass(frozen=True, slots=True)
class AccountName:
    full_name: str
    MAX_SEGMENT: int = 255
    MAX_FULL: int = 1024
    segments: Sequence[str] = field(init=False, repr=False, default_factory=tuple)

    def __post_init__(self):  # type: ignore[override]
        raw = self.full_name
        if not raw or not isinstance(raw, str):  # noqa: SIM103
            raise DomainError("Account full name must be non-empty string")
        if len(raw) > self.MAX_FULL:
            raise DomainError("Account full name too long")
        if raw.startswith(":") or raw.endswith(":") or "::" in raw:
            raise DomainError("Account full name has empty segment")
        segments = raw.split(":")
        for seg in segments:
            if len(seg) > self.MAX_SEGMENT:
                raise DomainError("Account name segment too long")
            if any(not (c.isalnum() or c == "_") for c in seg):
                raise DomainError("Account name segments must be alnum/_ only")
        object.__setattr__(self, "full_name", raw)
        object.__setattr__(self, "segments", tuple(segments))

    @property
    def name(self) -> str:
        return self.segments[-1]

    @property
    def parent(self) -> AccountName | None:
        if len(self.segments) == 1:
            return None
        return AccountName(":".join(self.segments[:-1]))

    def path(self) -> Sequence[str]:  # pragma: no cover - simple
        return self.segments

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.full_name


class EntrySide(str, Enum):
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"

    @property
    def is_debit(self) -> bool:
        return self is EntrySide.DEBIT

    @property
    def is_credit(self) -> bool:
        return self is EntrySide.CREDIT


@dataclass(frozen=True, slots=True)
class ExchangeRate:
    value: Decimal

    @classmethod
    def from_number(cls, number: int | float | str | Decimal) -> ExchangeRate:
        try:
            dec = Decimal(str(number))
        except (InvalidOperation, ValueError) as exc:  # noqa: PERF203
            raise DomainError("Invalid exchange rate") from exc
        if dec <= 0:
            raise DomainError("Exchange rate must be > 0")
        # Normalize to 10 decimal places for deterministic comparisons.
        dec = dec.quantize(Decimal("1.0000000000"), rounding=ROUND_HALF_UP)
        return cls(dec)

    def __post_init__(self):  # type: ignore[override]
        if self.value <= 0:
            raise DomainError("Exchange rate must be > 0")

    def __float__(self) -> float:  # pragma: no cover - trivial
        return float(self.value)


@dataclass(frozen=True, slots=True)
class EntryLine:
    side: EntrySide
    account: AccountName
    amount: Decimal
    currency: CurrencyCode
    exchange_rate: ExchangeRate

    @classmethod
    def create(
        cls,
        side: EntrySide,
        account: AccountName | str,
        amount: int | str | Decimal | float,
        currency: CurrencyCode | str,
        exchange_rate: ExchangeRate | int | float | Decimal | str = 1,
    ) -> EntryLine:
        if isinstance(account, str):
            account = AccountName(account)
        if isinstance(currency, str):
            currency = CurrencyCode(currency)
        try:
            dec_amount = Decimal(str(amount))
        except (InvalidOperation, ValueError) as exc:  # noqa: PERF203
            raise DomainError("Invalid amount") from exc
        if dec_amount <= 0:
            raise DomainError("Amount must be > 0")
        if not isinstance(exchange_rate, ExchangeRate):
            exchange_rate = ExchangeRate.from_number(exchange_rate)
        return cls(side=side, account=account, amount=dec_amount, currency=currency, exchange_rate=exchange_rate)

    def amount_in_base(self) -> Decimal:
        """Amount converted to base (divide by exchange rate)."""
        return self.amount / self.exchange_rate.value


@dataclass(frozen=True, slots=True)
class TransactionVO:
    lines: tuple[EntryLine, ...]
    memo: str = ""
    occurred_at: datetime = datetime.now(UTC)

    def __post_init__(self):  # type: ignore[override]
        if not self.lines:
            raise DomainError("Transaction must have lines")
        debit = Decimal(0)
        credit = Decimal(0)
        base_currency: CurrencyCode | None = None
        for line in self.lines:
            if base_currency is None:
                base_currency = line.currency
            amount_base = line.amount / line.exchange_rate.value
            if line.side.is_debit:
                debit += amount_base
            else:
                credit += amount_base
        if debit.quantize(Decimal("1.0000000000")) != credit.quantize(Decimal("1.0000000000")):
            raise DomainError("Transaction not balanced (debits != credits in base)")

    @classmethod
    def from_lines(cls, lines: Iterable[EntryLine], memo: str = "", occurred_at: datetime | None = None) -> TransactionVO:
        return cls(lines=tuple(lines), memo=memo, occurred_at=occurred_at or datetime.now(UTC))

    @property
    def debit_lines(self) -> tuple[EntryLine, ...]:  # pragma: no cover
        return tuple(line for line in self.lines if line.side.is_debit)

    @property
    def credit_lines(self) -> tuple[EntryLine, ...]:  # pragma: no cover
        return tuple(line for line in self.lines if line.side.is_credit)

    @property
    def total_base_debit(self) -> Decimal | Literal[0]:
        return sum(line.amount_in_base() for line in self.lines if line.side.is_debit)

    @property
    def total_base_credit(self) -> Decimal | Literal[0]:
        return sum(line.amount_in_base() for line in self.lines if line.side.is_credit)
