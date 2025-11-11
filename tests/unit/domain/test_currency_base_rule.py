from decimal import getcontext

import pytest

from domain.currencies import BaseCurrencyRule, Currency, get_base_currency


def test_set_base_preserves_other_rates():
    # Snapshot global context
    orig_prec = getcontext().prec
    orig_rounding = getcontext().rounding

    usd = Currency("usd", is_base=True)
    eur = Currency("eur")
    jpy = Currency("jpy")

    eur_rate_before = eur.set_rate(0.9234567)
    jpy_rate_before = jpy.set_rate(151.2345678)

    chosen = BaseCurrencyRule.ensure_single_base([usd, eur, jpy], new_base_code="EUR")

    assert chosen is eur
    assert eur.is_base is True
    assert usd.is_base is False
    assert jpy.is_base is False

    # Rates of non-base currencies remain unchanged (quantized to 6 places)
    assert eur.rate_to_base == eur_rate_before
    assert jpy.rate_to_base == jpy_rate_before

    # Global Decimal context must not be changed by operations
    assert getcontext().prec == orig_prec
    assert getcontext().rounding == orig_rounding


def test_clear_base():
    usd = Currency("USD", is_base=True)
    eur = Currency("EUR")
    jpy = Currency("JPY")

    BaseCurrencyRule.clear_base([usd, eur, jpy])

    assert usd.is_base is False
    assert eur.is_base is False
    assert jpy.is_base is False
    assert get_base_currency([usd, eur, jpy]) is None


def test_set_base_missing_code_raises():
    usd = Currency("USD", is_base=True)
    eur = Currency("EUR")

    with pytest.raises(Exception) as exc:
        BaseCurrencyRule.ensure_single_base([usd, eur], new_base_code="CHF")
    msg = str(exc.value)
    assert "Currency not found" in msg or "not found" in msg
