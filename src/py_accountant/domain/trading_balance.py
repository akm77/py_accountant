"""Raw trading balance aggregation.

Public API:
- RawBalanceLine: immutable dataclass with currency totals (debit, credit, net).
- RawAggregator: groups validated LedgerEntry lines by currency and returns totals.
- ConvertedBalanceLine: immutable dataclass with original and base-currency totals.
- ConvertedAggregator: aggregates like RawAggregator and converts to base currency.

Notes:
- Aggregation is performed in a single pass without converting to base currency.
- Rounding uses domain.quantize.money_quantize (2dp, HALF_EVEN) and does not
  mutate the global Decimal context.
- No infrastructure dependencies; domain-only.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal

from .currencies import Currency, get_base_currency
from .errors import ValidationError
from .ledger import EntrySide, LedgerEntry
from .quantize import money_quantize, rate_quantize


@dataclass(slots=True, frozen=True)
class RawBalanceLine:
    """A single currency aggregation line.

    Attributes:
        currency_code: Upper-case currency code (3..10 chars).
        debit: Total debit for the currency, quantized to 2dp, >= 0.
        credit: Total credit for the currency, quantized to 2dp, >= 0.
        net: Net balance (debit - credit), quantized to 2dp (may be negative/zero/positive).
    """

    currency_code: str
    debit: Decimal
    credit: Decimal
    net: Decimal


class RawAggregator:
    """Aggregate validated ledger entries by currency without FX conversion.

    Usage: RawAggregator().aggregate(lines) -> list[RawBalanceLine] sorted by currency code.
    """

    def aggregate(self, lines: Iterable[LedgerEntry]) -> list[RawBalanceLine]:
        """Group lines by currency and produce rounded totals.

        Args:
            lines: Iterable of LedgerEntry objects. Can be empty.

        Returns:
            List of RawBalanceLine sorted by currency_code ascending. Empty if input is empty.

        Raises:
            ValidationError: If an input element is not a LedgerEntry or has an invalid side.
        """
        # Single-pass accumulation of raw Decimal amounts per currency and side
        debit_totals: dict[str, Decimal] = {}
        credit_totals: dict[str, Decimal] = {}

        for item in lines:
            if not isinstance(item, LedgerEntry):  # safety guard for unexpected inputs
                raise ValidationError("Input must be LedgerEntry instances")

            code = (item.currency_code or "").strip().upper()
            if not (3 <= len(code) <= 10):  # ultra-conservative check (already enforced by LedgerEntry)
                raise ValidationError(f"Invalid currency code: {item.currency_code!r}")

            if item.side == EntrySide.DEBIT:
                debit_totals[code] = debit_totals.get(code, Decimal("0")) + item.amount
            elif item.side == EntrySide.CREDIT:
                credit_totals[code] = credit_totals.get(code, Decimal("0")) + item.amount
            else:
                # Should be unreachable because LedgerEntry validates, but guard anyway
                raise ValidationError(f"Invalid entry side: {item.side!r}")

        # Build results with rounding at the end per currency
        if not debit_totals and not credit_totals:
            return []

        codes = sorted(set(debit_totals.keys()) | set(credit_totals.keys()))
        results: list[RawBalanceLine] = []
        for code in codes:
            debit_q = money_quantize(debit_totals.get(code, Decimal("0")))
            credit_q = money_quantize(credit_totals.get(code, Decimal("0")))
            net_q = money_quantize(debit_q - credit_q)
            results.append(
                RawBalanceLine(
                    currency_code=code,
                    debit=debit_q,
                    credit=credit_q,
                    net=net_q,
                )
            )
        return results


@dataclass(slots=True, frozen=True)
class ConvertedBalanceLine:
    """Aggregation line with base-currency conversion.

    Attributes:
        currency_code: Upper-case currency code from entries (3..10 chars).
        base_currency_code: Upper-case base currency code, detected or provided.
        used_rate: FX rate to base (rate_quantize to 6 d.p.; 1 for base currency).
        debit: Original debit total (2 d.p., >= 0).
        credit: Original credit total (2 d.p., >= 0).
        net: Original net (debit - credit) rounded to 2 d.p.
        debit_base: Debit total converted to base (2 d.p., >= 0).
        credit_base: Credit total converted to base (2 d.p., >= 0).
        net_base: Net in base (debit_base - credit_base) rounded to 2 d.p.
    """

    currency_code: str
    base_currency_code: str
    used_rate: Decimal
    debit: Decimal
    credit: Decimal
    net: Decimal
    debit_base: Decimal
    credit_base: Decimal
    net_base: Decimal


class ConvertedAggregator:
    """Aggregate validated ledger entries by currency and convert to base currency.

    Usage: ConvertedAggregator().aggregate(lines, currencies, base_code=None)
           -> list[ConvertedBalanceLine] sorted by currency code.
    """

    def aggregate(
        self,
        lines: Iterable[LedgerEntry],
        currencies: Sequence[Currency] | Mapping[str, Currency],
        base_code: str | None = None,
    ) -> list[ConvertedBalanceLine]:
        """Group lines by currency, compute totals and convert to the base currency.

        Args:
            lines: Iterable of LedgerEntry instances. Can be empty.
            currencies: Collection of Currency objects (sequence or mapping); codes are
                matched case-insensitively.
            base_code: Optional explicit base currency code; if omitted, detected via
                get_base_currency(currencies).

        Returns:
            List of ConvertedBalanceLine sorted by currency_code (ASC). Empty for empty input.

        Raises:
            ValidationError: If an input element is not a LedgerEntry; if a currency in
                entries is absent in `currencies`; if base currency cannot be determined;
                or for non-base currencies when rate_to_base is missing or non-positive.
        """
        # Single-pass accumulation of raw Decimal amounts per currency and side
        raw_debit: dict[str, Decimal] = {}
        raw_credit: dict[str, Decimal] = {}

        for item in lines:
            if not isinstance(item, LedgerEntry):
                raise ValidationError("Input must be LedgerEntry instances")
            code = (item.currency_code or "").strip().upper()
            if not (3 <= len(code) <= 10):
                raise ValidationError(f"Invalid currency code: {item.currency_code!r}")
            if item.side == EntrySide.DEBIT:
                raw_debit[code] = raw_debit.get(code, Decimal("0")) + item.amount
            elif item.side == EntrySide.CREDIT:
                raw_credit[code] = raw_credit.get(code, Decimal("0")) + item.amount
            else:
                raise ValidationError(f"Invalid entry side: {item.side!r}")

        # Early return for empty input
        if not raw_debit and not raw_credit:
            return []

        # Normalize currencies to mapping and list for base detection
        if isinstance(currencies, Mapping):
            cur_map: dict[str, Currency] = { (k or "").strip().upper(): v for k, v in currencies.items() }
            cur_values = list(cur_map.values())
        else:
            cur_values = list(currencies)
            cur_map = { c.code.strip().upper(): c for c in cur_values }

        # Determine base currency
        if base_code is not None:
            base_norm = (base_code or "").strip().upper()
            base_currency = cur_map.get(base_norm)
            if base_currency is None:
                raise ValidationError(f"Base currency not found: {base_code!r}")
            base_code_norm = base_currency.code
        else:
            base_currency = get_base_currency(cur_values)
            if base_currency is None:
                raise ValidationError("Base currency is not defined")
            base_code_norm = base_currency.code

        # Build per-currency results
        codes = sorted(set(raw_debit.keys()) | set(raw_credit.keys()))
        results: list[ConvertedBalanceLine] = []

        for code in codes:
            currency = cur_map.get(code)
            if currency is None:
                raise ValidationError(f"Unknown currency in entry: {code!r}")

            # Original totals rounded for DTO
            debit_q = money_quantize(raw_debit.get(code, Decimal("0")))
            credit_q = money_quantize(raw_credit.get(code, Decimal("0")))
            net_q = money_quantize(debit_q - credit_q)

            # Determine rate and convert totals to base currency
            if code == base_code_norm:
                used_rate_num = Decimal("1")
            else:
                rate = currency.rate_to_base
                if rate is None:
                    raise ValidationError(f"Missing rate_to_base for currency: {currency.code}")
                if rate <= 0:
                    raise ValidationError(f"Non-positive rate_to_base for currency: {currency.code}")
                used_rate_num = rate
            used_rate_dto = rate_quantize(used_rate_num)

            # Convert raw totals (pre-rounded) and then quantize to money
            debit_base_q = money_quantize(raw_debit.get(code, Decimal("0")) * used_rate_num)
            credit_base_q = money_quantize(raw_credit.get(code, Decimal("0")) * used_rate_num)
            net_base_q = money_quantize(debit_base_q - credit_base_q)

            results.append(
                ConvertedBalanceLine(
                    currency_code=code,
                    base_currency_code=base_code_norm,
                    used_rate=used_rate_dto,
                    debit=debit_q,
                    credit=credit_q,
                    net=net_q,
                    debit_base=debit_base_q,
                    credit_base=credit_base_q,
                    net_base=net_base_q,
                )
            )

        return results

