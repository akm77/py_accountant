from __future__ import annotations

from decimal import Decimal, getcontext

import pytest

from domain.errors import ValidationError
from domain.ledger import EntrySide, LedgerEntry
from domain.trading_balance import RawAggregator, RawBalanceLine


def test_empty_returns_no_lines():
    assert RawAggregator().aggregate([]) == []


def test_single_currency_aggregate():
    lines = [
        LedgerEntry(EntrySide.DEBIT, 100, "USD"),
        LedgerEntry(EntrySide.CREDIT, 30, "USD"),
        LedgerEntry(EntrySide.DEBIT, 10, "USD"),
    ]
    res = RawAggregator().aggregate(lines)
    assert res == [
        RawBalanceLine(
            currency_code="USD",
            debit=Decimal("110.00"),
            credit=Decimal("30.00"),
            net=Decimal("80.00"),
        )
    ]


def test_multi_currency_aggregate_separate_groups():
    lines = [
        LedgerEntry(EntrySide.DEBIT, 50, "USD"),
        LedgerEntry(EntrySide.CREDIT, 20, "EUR"),
        LedgerEntry(EntrySide.CREDIT, 5, "USD"),
        LedgerEntry(EntrySide.DEBIT, 21, "EUR"),
    ]
    res = RawAggregator().aggregate(lines)
    assert res == [
        RawBalanceLine(
            currency_code="EUR",
            debit=Decimal("21.00"),
            credit=Decimal("20.00"),
            net=Decimal("1.00"),
        ),
        RawBalanceLine(
            currency_code="USD",
            debit=Decimal("50.00"),
            credit=Decimal("5.00"),
            net=Decimal("45.00"),
        ),
    ]


def test_rounding_half_even_each_currency():
    # EUR: debit 1.235 -> 1.24, credit implicitly 0 (no credit entries) -> 0.00, net 1.24
    # USD: debit 1.00, credit 0.005 -> 0.00 (HALF_EVEN), net 1.00
    lines = [
        LedgerEntry(EntrySide.DEBIT, Decimal("1.235"), "EUR"),
        LedgerEntry(EntrySide.DEBIT, Decimal("1.00"), "USD"),
        LedgerEntry(EntrySide.CREDIT, Decimal("0.005"), "USD"),
    ]
    res = RawAggregator().aggregate(lines)
    assert res == [
        RawBalanceLine(
            currency_code="EUR",
            debit=Decimal("1.24"),
            credit=Decimal("0.00"),
            net=Decimal("1.24"),
        ),
        RawBalanceLine(
            currency_code="USD",
            debit=Decimal("1.00"),
            credit=Decimal("0.00"),
            net=Decimal("1.00"),
        ),
    ]


def test_preserve_decimal_context():
    ctx = getcontext().copy()
    lines = [LedgerEntry(EntrySide.DEBIT, 1, "USD"), LedgerEntry(EntrySide.CREDIT, 1, "USD")]
    RawAggregator().aggregate(lines)
    ctx_after = getcontext()
    assert ctx.prec == ctx_after.prec
    assert ctx.rounding == ctx_after.rounding


def test_reject_non_ledger_entry_input_guard():
    with pytest.raises(ValidationError):
        RawAggregator().aggregate([{"side": "DEBIT", "amount": 10, "currency_code": "USD"}])
