from __future__ import annotations

from decimal import Decimal

from py_accountant.domain.services.exchange_rate_policy import ExchangeRatePolicy


def test_weighted_average_sequence_and_none_prev():
    p = ExchangeRatePolicy(mode="weighted_average")
    # No previous -> returns observed and count=1
    r1 = p.apply(None, Decimal("1.0"))
    assert r1 == Decimal("1.0")
    # prev valid -> average with count logic
    r2 = p.apply(Decimal("1.0"), Decimal("2.0"))  # (1+2)/2=1.5
    assert r2 == Decimal("1.5")
    r3 = p.apply(r2, Decimal("1.0"))  # (1.5*2 + 1)/3 = 1.333...
    assert str(r3).startswith("1.33")

