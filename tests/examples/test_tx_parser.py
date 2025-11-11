"""Tests for the /tx payload parser (iteration 3).

Covers required happy path and error scenarios plus a few optional edge cases.
"""

import os
import sys
from decimal import Decimal

# Ensure repository root is on sys.path so 'examples' is importable
_THIS_DIR = os.path.dirname(__file__)
_REPO_ROOT = os.path.abspath(os.path.join(_THIS_DIR, os.pardir, os.pardir))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import pytest  # noqa: E402

from examples.telegram_bot.handlers import (  # noqa: E402,I001
    TxFormatError,
    parse_tx_payload,
)


def test_parse_tx_payload_happy_two_lines():
    raw = "DEBIT:Cash:100:USD;CREDIT:Revenue:100:USD"
    lines = parse_tx_payload(raw)
    assert len(lines) == 2
    assert lines[0].side == "DEBIT"
    assert lines[0].account == "Cash"
    assert lines[0].amount == Decimal("100")
    assert lines[0].currency == "USD"
    assert lines[0].rate is None
    assert lines[1].side == "CREDIT"
    assert lines[1].account == "Revenue"
    assert lines[1].amount == Decimal("100")
    assert lines[1].currency == "USD"
    assert lines[1].rate is None


def test_parse_tx_payload_invalid_side():
    raw = "INCORRECT:Cash:100:USD;CREDIT:Revenue:100:USD"
    with pytest.raises(TxFormatError) as exc:
        parse_tx_payload(raw)
    err = exc.value
    assert err.line_index == 0
    assert err.reason == "invalid_side"


def test_parse_tx_payload_negative_amount():
    raw = "DEBIT:Cash:-5:USD;CREDIT:Revenue:5:USD"
    with pytest.raises(TxFormatError) as exc:
        parse_tx_payload(raw)
    err = exc.value
    assert err.line_index == 0
    assert err.reason == "non_positive_amount"

# Optional edge cases

def test_parse_tx_payload_with_rate():
    raw = "DEBIT:Cash:100:USD:1.0;CREDIT:Sales:100:USD"
    lines = parse_tx_payload(raw)
    assert len(lines) == 2
    assert lines[0].rate == Decimal("1.0")
    assert lines[1].rate is None


def test_parse_tx_payload_account_with_colons():
    raw = "DEBIT:Assets:Current:Cash:100:USD;CREDIT:Income:Sales:100:USD"
    lines = parse_tx_payload(raw)
    assert len(lines) == 2
    assert lines[0].account == "Assets:Current:Cash"
    assert lines[1].account == "Income:Sales"


def test_parse_tx_payload_trailing_semicolons():
    raw = "DEBIT:Cash:100:USD;CREDIT:Revenue:100:USD;;;"
    lines = parse_tx_payload(raw)
    assert len(lines) == 2


def test_parse_tx_payload_empty_raw():
    assert parse_tx_payload("") == []


def test_parse_tx_payload_invalid_currency():
    raw = "DEBIT:Cash:100:US1;"
    with pytest.raises(TxFormatError) as exc:
        parse_tx_payload(raw)
    assert exc.value.reason == "invalid_currency"


def test_parse_tx_payload_invalid_rate_non_decimal():
    raw = "DEBIT:Cash:100:USD:abc"
    # 'abc' should not be treated as rate; parts are only 5 tokens so we check outcome:
    # parts -> ['DEBIT','Cash','100','USD','abc'] -> rate parsing fails => has_rate False
    # amount candidate becomes 'USD' (incorrect) leading to invalid_amount when parsing Decimal('USD')
    with pytest.raises(TxFormatError) as exc:
        parse_tx_payload(raw)
    assert exc.value.reason in {"invalid_amount", "invalid_currency"}  # depending on interpretation
