from __future__ import annotations

from dataclasses import FrozenInstanceError, fields
from decimal import Decimal

import pytest

from application.dto.models import TradingBalanceLineDetailed, TradingBalanceLineSimple


def test_simple_line_without_converted_fields() -> None:
    line = TradingBalanceLineSimple(
        currency_code="USD",
        debit=Decimal("10"),
        credit=Decimal("2"),
        net=Decimal("8"),
    )

    # Attribute presence checks (negative)
    assert not hasattr(line, "used_rate")
    assert not hasattr(line, "debit_base")
    assert not hasattr(line, "credit_base")
    assert not hasattr(line, "net_base")
    assert not hasattr(line, "base_currency_code")

    # Dataclass field enumeration (ensure only expected fields)
    names = [f.name for f in fields(line)]
    assert names == ["currency_code", "debit", "credit", "net"]

    # Type checks
    assert isinstance(line.debit, Decimal)
    assert isinstance(line.credit, Decimal)
    assert isinstance(line.net, Decimal)
    assert line.net == Decimal("8")


def test_detailed_line_contains_conversion() -> None:
    line = TradingBalanceLineDetailed(
        currency_code="EUR",
        base_currency_code="USD",
        debit=Decimal("100"),
        credit=Decimal("40"),
        net=Decimal("60"),
        used_rate=Decimal("1.085000"),  # assumed already normalized to 6 places
        debit_base=Decimal("108.500000"),
        credit_base=Decimal("43.400000"),
        net_base=Decimal("65.100000"),
    )

    # Positive attribute presence
    assert hasattr(line, "used_rate")
    assert hasattr(line, "debit_base")
    assert hasattr(line, "credit_base")
    assert hasattr(line, "net_base")
    assert hasattr(line, "base_currency_code")

    # Field enumeration
    names = [f.name for f in fields(line)]
    assert names == [
        "currency_code",
        "base_currency_code",
        "debit",
        "credit",
        "net",
        "used_rate",
        "debit_base",
        "credit_base",
        "net_base",
    ]

    # Value integrity
    assert line.used_rate == Decimal("1.085000")
    assert line.debit_base == Decimal("108.500000")
    assert line.net_base == Decimal("65.100000")

    # Type checks
    for attr in [
        line.debit,
        line.credit,
        line.net,
        line.used_rate,
        line.debit_base,
        line.credit_base,
        line.net_base,
    ]:
        assert isinstance(attr, Decimal)


def test_docstrings_present_public_classes() -> None:
    # Ensure docstrings exist (non-empty) on public classes
    assert TradingBalanceLineSimple.__doc__ and TradingBalanceLineSimple.__doc__.strip()
    assert TradingBalanceLineDetailed.__doc__ and TradingBalanceLineDetailed.__doc__.strip()


def test_frozen_slots_behavior() -> None:
    line = TradingBalanceLineSimple(currency_code="JPY", debit=Decimal("5"), credit=Decimal("1"), net=Decimal("4"))
    attr_name = "debit"
    with pytest.raises(FrozenInstanceError):
        setattr(line, attr_name, Decimal("6"))

    detailed = TradingBalanceLineDetailed(
        currency_code="JPY",
        base_currency_code="USD",
        debit=Decimal("5"),
        credit=Decimal("1"),
        net=Decimal("4"),
        used_rate=Decimal("0.006700"),
        debit_base=Decimal("0.033500"),
        credit_base=Decimal("0.006700"),
        net_base=Decimal("0.026800"),
    )
    attr_name2 = "used_rate"
    with pytest.raises(FrozenInstanceError):
        setattr(detailed, attr_name2, Decimal("0.007000"))
