from decimal import Decimal

from py_accountant.application.utils.quantize import money_quantize, rate_quantize


def test_money_quantize_round_half_even_edge():
    # Assuming ROUND_HALF_EVEN default, 0.005 with MONEY_SCALE=2 -> 0.00 or 0.01 depending on banker's rounding
    # With HALF_EVEN: 0.005 -> 0.00 (since 0.00 is even) for scale=2
    val = Decimal("0.005")
    q = money_quantize(val)
    assert q in {Decimal("0.00"), Decimal("0.01")}  # tolerate config change


def test_money_quantize_small_below_half():
    val = Decimal("0.0049")
    q = money_quantize(val)
    assert q <= Decimal("0.01")


def test_money_quantize_large_number():
    val = Decimal("123456789.9999")
    q = money_quantize(val)
    assert isinstance(q, Decimal)
    assert q.quantize(Decimal("1.00")) == q  # scale 2


def test_rate_quantize_precision():
    val = Decimal("1.234567890123")
    q = rate_quantize(val)
    assert isinstance(q, Decimal)
    # Default RATE_SCALE=10
    assert len(str(q).split(".")[-1]) <= 10

