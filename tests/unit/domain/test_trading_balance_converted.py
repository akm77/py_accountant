from __future__ import annotations

from decimal import Decimal, getcontext

import pytest

from py_accountant.domain.currencies import Currency
from py_accountant.domain.errors import ValidationError
from py_accountant.domain.ledger import EntrySide, LedgerEntry
from py_accountant.domain.trading_balance import (
    ConvertedAggregator,
    ConvertedBalanceLine,
)


def test_empty_returns_no_lines_converted():
    usd = Currency("USD", is_base=True)
    res = ConvertedAggregator().aggregate([], [usd])
    assert res == []


def test_single_currency_base_passthrough():
    usd = Currency("USD", is_base=True)
    lines = [
        LedgerEntry(EntrySide.DEBIT, 100, "USD"),
        LedgerEntry(EntrySide.CREDIT, 30, "USD"),
        LedgerEntry(EntrySide.DEBIT, 10, "USD"),
    ]
    res = ConvertedAggregator().aggregate(lines, [usd], base_code="USD")
    assert res == [
        ConvertedBalanceLine(
            currency_code="USD",
            base_currency_code="USD",
            used_rate=Decimal("1.000000"),
            debit=Decimal("110.00"),
            credit=Decimal("30.00"),
            net=Decimal("80.00"),
            debit_base=Decimal("110.00"),
            credit_base=Decimal("30.00"),
            net_base=Decimal("80.00"),
        )
    ]


def test_single_nonbase_with_rate():
    usd = Currency("USD", is_base=True)
    eur = Currency("EUR", rate_to_base=Decimal("1.1"))
    lines = [
        LedgerEntry(EntrySide.DEBIT, 50, "EUR"),
        LedgerEntry(EntrySide.CREDIT, 5, "EUR"),
    ]
    res = ConvertedAggregator().aggregate(lines, [usd, eur], base_code="USD")
    assert res == [
        ConvertedBalanceLine(
            currency_code="EUR",
            base_currency_code="USD",
            used_rate=Decimal("1.100000"),
            debit=Decimal("50.00"),
            credit=Decimal("5.00"),
            net=Decimal("45.00"),
            debit_base=Decimal("55.00"),
            credit_base=Decimal("5.50"),
            net_base=Decimal("49.50"),
        )
    ]


def test_multi_currency_mixed_and_sorting():
    usd = Currency("USD", is_base=True)
    eur = Currency("EUR", rate_to_base=Decimal("1.1"))
    lines = [
        LedgerEntry(EntrySide.DEBIT, 20, "USD"),
        LedgerEntry(EntrySide.CREDIT, 10, "EUR"),
        LedgerEntry(EntrySide.DEBIT, 22, "EUR"),
    ]
    res = ConvertedAggregator().aggregate(lines, [usd, eur], base_code="USD")
    assert res == [
        ConvertedBalanceLine(
            currency_code="EUR",
            base_currency_code="USD",
            used_rate=Decimal("1.100000"),
            debit=Decimal("22.00"),
            credit=Decimal("10.00"),
            net=Decimal("12.00"),
            debit_base=Decimal("24.20"),
            credit_base=Decimal("11.00"),
            net_base=Decimal("13.20"),
        ),
        ConvertedBalanceLine(
            currency_code="USD",
            base_currency_code="USD",
            used_rate=Decimal("1.000000"),
            debit=Decimal("20.00"),
            credit=Decimal("0.00"),
            net=Decimal("20.00"),
            debit_base=Decimal("20.00"),
            credit_base=Decimal("0.00"),
            net_base=Decimal("20.00"),
        ),
    ]


def test_rounding_half_even_in_base():
    usd = Currency("USD", is_base=True)
    eur = Currency("EUR", rate_to_base=Decimal("0.5"))
    lines = [
        LedgerEntry(EntrySide.CREDIT, Decimal("0.01"), "EUR"),
        LedgerEntry(EntrySide.DEBIT, Decimal("0.035"), "EUR"),
    ]
    res = ConvertedAggregator().aggregate(lines, [usd, eur], base_code="USD")
    assert res == [
        ConvertedBalanceLine(
            currency_code="EUR",
            base_currency_code="USD",
            used_rate=Decimal("0.500000"),
            debit=Decimal("0.04"),
            credit=Decimal("0.01"),
            net=Decimal("0.03"),
            debit_base=Decimal("0.02"),
            credit_base=Decimal("0.00"),
            net_base=Decimal("0.02"),
        )
    ]


def test_missing_rate_raises_for_non_base():
    usd = Currency("USD", is_base=True)
    eur = Currency("EUR")  # no rate set
    lines = [LedgerEntry(EntrySide.DEBIT, 1, "EUR")]
    with pytest.raises(ValidationError):
        ConvertedAggregator().aggregate(lines, [usd, eur], base_code="USD")


@pytest.mark.parametrize("bad_rate", [Decimal("0"), Decimal("-1"), Decimal("-0.01")])
def test_non_positive_rate_raises(bad_rate: Decimal):
    usd = Currency("USD", is_base=True)
    eur = Currency("EUR")
    # Bypass setter validation to simulate downstream corrupt data
    eur.rate_to_base = bad_rate
    lines = [LedgerEntry(EntrySide.DEBIT, 1, "EUR")]
    with pytest.raises(ValidationError):
        ConvertedAggregator().aggregate(lines, [usd, eur], base_code="USD")


def test_unknown_currency_line_raises():
    usd = Currency("USD", is_base=True)
    lines = [LedgerEntry(EntrySide.DEBIT, 1, "EUR")]
    with pytest.raises(ValidationError):
        ConvertedAggregator().aggregate(lines, [usd], base_code="USD")


def test_base_detection_via_get_base_currency():
    # Base is determined from currencies (USD.is_base=True), base_code not passed
    usd = Currency("USD", is_base=True)
    eur = Currency("EUR", rate_to_base=Decimal("1.1"))
    lines = [LedgerEntry(EntrySide.DEBIT, 10, "USD")]
    res = ConvertedAggregator().aggregate(lines, [usd, eur])
    assert res == [
        ConvertedBalanceLine(
            currency_code="USD",
            base_currency_code="USD",
            used_rate=Decimal("1.000000"),
            debit=Decimal("10.00"),
            credit=Decimal("0.00"),
            net=Decimal("10.00"),
            debit_base=Decimal("10.00"),
            credit_base=Decimal("0.00"),
            net_base=Decimal("10.00"),
        )
    ]


def test_preserve_decimal_context_converted():
    ctx_before = getcontext().copy()
    usd = Currency("USD", is_base=True)
    lines = [LedgerEntry(EntrySide.DEBIT, 1, "USD"), LedgerEntry(EntrySide.CREDIT, 1, "USD")]
    ConvertedAggregator().aggregate(lines, [usd], base_code="USD")
    ctx_after = getcontext()
    assert ctx_before.prec == ctx_after.prec
    assert ctx_before.rounding == ctx_after.rounding


def test_input_guard_non_ledger_entry():
    usd = Currency("USD", is_base=True)
    with pytest.raises(ValidationError):
        ConvertedAggregator().aggregate([
            {"side": "DEBIT", "amount": 10, "currency_code": "USD"}
        ], [usd], base_code="USD")

