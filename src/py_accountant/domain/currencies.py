"""Domain currency value object and base currency rule.

Public API:
- Currency: code, is_base, rate_to_base with helpers to manage rate and base flag.
- BaseCurrencyRule: ensure a single base currency among a list, or clear base.
- get_base_currency: return current base or None.

No infrastructure dependencies. Rates are normalized via rate_quantize and must be
positive (> 0). The global Decimal context is not modified.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from .errors import ValidationError
from .quantize import rate_quantize


@dataclass(slots=True)
class Currency:
    """Currency value object with a code, base flag, and an optional rate to base.

    Notes:
    - `code` is normalized to upper-case and validated to length 3..10.
    - `rate_to_base` is stored as a Decimal when set via `set_rate`, quantized to
      six fractional digits using banker's rounding (rate_quantize).
    - Base currency may have `rate_to_base` as None; the rule engine manages base selection.
    """

    code: str
    is_base: bool = False
    rate_to_base: Decimal | None = field(default=None)

    def __post_init__(self) -> None:
        # Normalize and validate code
        normalized = (self.code or "").strip().upper()
        if not (3 <= len(normalized) <= 10):
            raise ValidationError(f"Invalid currency code length: {self.code!r}")
        self.code = normalized
        # If rate provided directly (rare), ensure it's Decimal-quantized
        if self.rate_to_base is not None:
            # Accept only positive rates
            if self.rate_to_base <= 0:
                raise ValidationError("Rate must be positive")
            self.rate_to_base = rate_quantize(self.rate_to_base)

    def set_rate(self, rate: Decimal | str | float | int) -> Decimal:
        """Set and normalize the currency's rate to base (> 0).

        Args:
            rate: The new rate value; accepted as Decimal/str/float/int.

        Returns:
            Decimal: The quantized rate stored on the object.
        """
        q = rate_quantize(rate)
        if q <= 0:
            raise ValidationError("Rate must be positive")
        self.rate_to_base = q
        return q

    def clear_rate(self) -> None:
        """Clear any stored rate to base (sets to None)."""
        self.rate_to_base = None

    def mark_base(self) -> None:
        """Mark this currency as the base currency (internal guard)."""
        self.is_base = True

    def unmark_base(self) -> None:
        """Remove base currency mark from this currency."""
        self.is_base = False


class BaseCurrencyRule:
    """Service to enforce a single base currency within a collection.

    This service does not modify or recalculate rates of other currencies.
    It only toggles the `is_base` flags to ensure a single base currency or
    clears the base flag from all currencies.
    """

    @staticmethod
    def ensure_single_base(currencies: list[Currency], new_base_code: str) -> Currency:
        """Ensure exactly one base currency exists, selecting `new_base_code`.

        Sets `is_base=True` for the matching currency and `False` for all others.
        Does not change `rate_to_base` values.

        Args:
            currencies: The in-memory list of currency objects to adjust.
            new_base_code: The code of the currency to become the base (case-insensitive).

        Returns:
            Currency: The currency object marked as base.

        Raises:
            ValidationError: If `new_base_code` is not found in the list.
        """
        code_norm = (new_base_code or "").strip().upper()
        target: Currency | None = None
        for c in currencies:
            if c.code == code_norm:
                target = c
                break
        if target is None:
            raise ValidationError(f"Currency not found: {new_base_code!r}")

        # Idempotent: mark target base; unmark others. No rate changes.
        for c in currencies:
            if c is target:
                c.mark_base()
            else:
                c.unmark_base()
        return target

    @staticmethod
    def clear_base(currencies: list[Currency]) -> None:
        """Clear base flag from all currencies; base may be temporarily absent."""
        for c in currencies:
            c.unmark_base()


def get_base_currency(currencies: list[Currency]) -> Currency | None:
    """Return the current base currency in the list or None if absent."""
    for c in currencies:
        if c.is_base:
            return c
    # TODO: Optionally validate duplicate base flags in future (repository-level uniqueness)
    return None

