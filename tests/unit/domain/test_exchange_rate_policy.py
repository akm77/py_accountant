from __future__ import annotations

from decimal import Decimal

from py_accountant.domain.services.exchange_rate_policy import ExchangeRatePolicy


def test_policy_last_write():
    p = ExchangeRatePolicy(mode="last_write")
    assert p.apply(Decimal("1.1"), Decimal("1.2")) == Decimal("1.2")


def test_policy_weighted_average():
    p = ExchangeRatePolicy(mode="weighted_average")
    res = p.apply(Decimal("1.0"), Decimal("1.2"))
    assert res == Decimal("1.1")

