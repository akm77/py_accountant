from __future__ import annotations

import decimal as dec
from decimal import ROUND_HALF_EVEN, Decimal

from py_accountant.infrastructure.config.settings import get_settings


def _make_quant(scale: int) -> Decimal:
    # Decimal tuple: sign=0, digits=(1,), exponent=-scale -> 10^-scale
    return Decimal((0, (1,), -scale))


def money_quantize(value: Decimal) -> Decimal:
    s = get_settings()
    quant = _make_quant(s.money_scale)
    rounding_mode = getattr(dec, s.rounding, ROUND_HALF_EVEN)
    return value.quantize(quant, rounding=rounding_mode)


def rate_quantize(value: Decimal) -> Decimal:
    s = get_settings()
    quant = _make_quant(s.rate_scale)
    rounding_mode = getattr(dec, s.rounding, ROUND_HALF_EVEN)
    return value.quantize(quant, rounding=rounding_mode)
