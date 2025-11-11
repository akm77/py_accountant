from decimal import Decimal, getcontext

from domain.quantize import money_quantize, rate_quantize


def test_money_quantize_rounds():
    assert money_quantize("1.2345") == Decimal("1.23")
    # half-even: .235 -> .24 because 23 is odd, so it goes to 24
    assert money_quantize("1.235") == Decimal("1.24")
    assert money_quantize(2) == Decimal("2.00")
    # float input processed via str() so -1.005 rounds to -1.00 (half-even toward even neighbor)
    assert money_quantize(-1.005) == Decimal("-1.00")


def test_rate_quantize_rounds():
    assert rate_quantize("1.23456789") == Decimal("1.234568")
    assert rate_quantize("0.0000004") == Decimal("0.000000")
    assert rate_quantize(1) == Decimal("1.000000")


def test_no_global_context_mutation():
    original_prec = getcontext().prec
    original_rounding = getcontext().rounding
    # Execute both functions
    _ = money_quantize("123.4567")
    _ = rate_quantize("1.234567")
    assert getcontext().prec == original_prec
    assert getcontext().rounding == original_rounding
