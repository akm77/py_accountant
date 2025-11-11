"""Ledger balance validation utilities.

Public API:
- EntrySide: enumeration of entry sides (DEBIT, CREDIT).
- LedgerEntry: simple value object for a ledger line.
- LedgerValidator: validator to ensure a set of entries is balanced in base currency.

The module is dependency-free except for domain-layer helpers. It does not modify
Decimal's global context and performs rounding via domain.quantize.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Any

from .currencies import Currency, get_base_currency
from .errors import DomainError, ValidationError
from .quantize import money_quantize


class EntrySide(str, Enum):
    """Ledger entry side: DEBIT or CREDIT."""

    DEBIT = "DEBIT"
    CREDIT = "CREDIT"


def _to_decimal(x: Decimal | int | str | float | Any) -> Decimal:
    if isinstance(x, Decimal):
        return x
    if isinstance(x, (int, str)):
        return Decimal(str(x))
    if isinstance(x, float):
        return Decimal(str(x))
    raise ValidationError(f"Unsupported amount type: {type(x)!r}")


@dataclass(slots=True, frozen=True)
class LedgerEntry:
    """A single ledger line with side, amount, and currency code.

    Notes:
    - `amount` is converted to Decimal on init and must be > 0.
    - `currency_code` is normalized to upper-case; length must be 3..10.
    - `side` can be EntrySide or a case-insensitive string of 'DEBIT'/'CREDIT'.
    """

    side: EntrySide | str
    amount: Decimal | int | str | float
    currency_code: str

    def __post_init__(self) -> None:  # type: ignore[override]
        # Normalize side
        side_val: EntrySide
        raw_side = self.side
        if isinstance(raw_side, EntrySide):
            side_val = raw_side
        elif isinstance(raw_side, str):
            normalized = raw_side.strip().upper()
            if normalized not in (EntrySide.DEBIT.value, EntrySide.CREDIT.value):
                raise ValidationError(f"Invalid entry side: {raw_side!r}")
            side_val = EntrySide(normalized)
        else:
            raise ValidationError(f"Invalid entry side type: {type(raw_side)!r}")
        object.__setattr__(self, "side", side_val)

        # Normalize amount
        amount_dec = _to_decimal(self.amount)
        if amount_dec <= 0:
            raise ValidationError("Amount must be positive")
        object.__setattr__(self, "amount", amount_dec)

        # Normalize currency code
        code = (self.currency_code or "").strip().upper()
        if not (3 <= len(code) <= 10):
            raise ValidationError(f"Invalid currency code length: {self.currency_code!r}")
        object.__setattr__(self, "currency_code", code)


class LedgerValidator:
    """Validate that ledger entries are balanced in the base currency.

    Use validate(...) to raise ValidationError/DomainError on problems; returns None otherwise.
    """

    @staticmethod
    def validate(
        lines: Iterable[LedgerEntry],
        currencies: Sequence[Currency] | Mapping[str, Currency],
        base_code: str | None = None,
    ) -> None:
        """Validate that debits equal credits in base currency.

        Args:
            lines: Iterable of LedgerEntry instances (non-empty).
            currencies: Collection of Currency objects; either a sequence or a mapping
                from currency code to Currency. Codes are matched case-insensitively.
            base_code: Optional explicit base currency code. If omitted, the base is
                inferred via get_base_currency(currencies).

        Raises:
            ValidationError: On invalid inputs, missing currencies or rates.
            DomainError: If the ledger is not balanced after conversion.
        """
        # Materialize lines and ensure non-empty
        materialized = list(lines)
        if not materialized:
            raise ValidationError("No ledger lines provided")

        # Normalize currencies into a dict code->Currency
        if isinstance(currencies, Mapping):
            cur_map = { (k or "").strip().upper(): v for k, v in currencies.items() }
            cur_values = list(cur_map.values())
        else:
            cur_values = list(currencies)
            cur_map = { c.code.strip().upper(): c for c in cur_values }
        if not cur_map:
            raise ValidationError("No currencies provided")

        # Determine base currency code
        if base_code is not None:
            base_norm = base_code.strip().upper()
            base_currency = cur_map.get(base_norm)
            if base_currency is None:
                raise ValidationError(f"Base currency not found: {base_code!r}")
            base_code_norm = base_currency.code  # ensure canonical code
        else:
            # Try to detect from provided currencies
            # get_base_currency expects a list
            base_currency = get_base_currency(cur_values)
            if base_currency is None:
                raise ValidationError("Base currency is not defined")
            base_code_norm = base_currency.code

        # Accumulators in base currency
        debit_total = Decimal("0")
        credit_total = Decimal("0")

        for entry in materialized:
            currency = cur_map.get(entry.currency_code)
            if currency is None:
                raise ValidationError(f"Unknown currency in entry: {entry.currency_code!r}")

            # Compute amount in base
            if currency.code == base_code_norm:
                amount_base = entry.amount
            else:
                rate = currency.rate_to_base
                if rate is None:
                    raise ValidationError(
                        f"Missing rate_to_base for currency: {currency.code}"
                    )
                if rate <= 0:
                    raise ValidationError(
                        f"Non-positive rate_to_base for currency: {currency.code}"
                    )
                amount_base = entry.amount * rate

            if entry.side == EntrySide.DEBIT:
                debit_total += amount_base
            elif entry.side == EntrySide.CREDIT:
                credit_total += amount_base
            else:
                # Should be unreachable due to LedgerEntry validation, but guard anyway
                raise ValidationError(f"Invalid entry side: {entry.side!r}")

        # Compare after money quantization (2dp, HALF_EVEN)
        if money_quantize(debit_total) != money_quantize(credit_total):
            raise DomainError("Ledger not balanced in base currency")
        # Success: return None
        return None
