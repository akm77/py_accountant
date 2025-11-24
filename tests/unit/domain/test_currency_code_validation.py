from __future__ import annotations

import pytest

from py_accountant.domain.value_objects import CurrencyCode, DomainError


def test_currency_code_min_length():
    with pytest.raises(DomainError):
        CurrencyCode("A")  # too short


def test_currency_code_max_length():
    long_code = "ABCDEFGHIJK"  # 11 chars > 10
    with pytest.raises(DomainError):
        CurrencyCode(long_code)


def test_currency_code_invalid_chars():
    with pytest.raises(DomainError):
        CurrencyCode("US D")  # space invalid
    with pytest.raises(DomainError):
        CurrencyCode("US$")  # symbol invalid


def test_currency_code_valid_range_and_chars():
    c = CurrencyCode("usd")
    assert c.code == "USD"
    c2 = CurrencyCode("EU_RO")
    assert c2.code == "EU_RO"

