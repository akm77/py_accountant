"""Domain quantization utilities.

Provides safe, deterministic quantization helpers for monetary amounts and FX rates
without mutating the global Decimal context. These functions concentrate rounding
rules in a single place for reuse across the domain layer.

Public API:
    money_quantize(x): 2 decimal places, ROUND_HALF_EVEN
    rate_quantize(x):  6 decimal places, ROUND_HALF_EVEN
"""
from __future__ import annotations

from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from typing import Any

_MONEY_PLACES = Decimal("0.01")  # Two fractional digits
_RATE_PLACES = Decimal("0.000001")  # Six fractional digits


def _to_decimal(x: Decimal | str | int | float | Any) -> Decimal:
    """Convert supported primitive/Decimal inputs to Decimal safely.

    Floats are converted via str(x) to avoid binary floating artifacts.
    Unsupported types will raise a ValueError.
    """
    if isinstance(x, Decimal):
        return x
    if isinstance(x, (int, str)):
        return Decimal(str(x))
    if isinstance(x, float):
        return Decimal(str(x))
    raise ValueError(f"Unsupported type for quantization: {type(x)!r}")


def money_quantize(x: Decimal | str | int | float) -> Decimal:
    """Quantize a monetary amount to 2 decimal places using HALF-EVEN.

    The function does not modify the global Decimal context; rounding is applied
    within a local context copy. Suitable for all currency amounts in the system.

    Args:
        x: Source amount as Decimal, str, int, or float.

    Returns:
        Decimal: Amount rounded to two fractional digits (banker's rounding).
    """
    value = _to_decimal(x)
    with localcontext() as ctx:  # local copy; modifications stay here
        ctx.rounding = ROUND_HALF_EVEN
        return value.quantize(_MONEY_PLACES, rounding=ROUND_HALF_EVEN)


def rate_quantize(x: Decimal | str | int | float) -> Decimal:
    """Quantize an FX rate to 6 decimal places using HALF-EVEN.

    Does not mutate the global Decimal context. Precision of six digits is
    sufficient for all internal FX computations.

    Args:
        x: Source rate as Decimal, str, int, or float.

    Returns:
        Decimal: Rate rounded to six fractional digits (banker's rounding).
    """
    value = _to_decimal(x)
    with localcontext() as ctx:
        ctx.rounding = ROUND_HALF_EVEN
        return value.quantize(_RATE_PLACES, rounding=ROUND_HALF_EVEN)

