from decimal import Decimal

import pytest

from py_accountant.domain import (
    AccountName,
    CurrencyCode,
    DomainError,
    EntryLine,
    EntrySide,
    ExchangeRate,
    TransactionVO,
)


def test_currency_code_normalization():
    c = CurrencyCode("usd")
    assert c.code == "USD"
    with pytest.raises(DomainError):
        CurrencyCode("")
    with pytest.raises(DomainError):
        CurrencyCode("toolongcurrencycode")


def test_account_name_segments_and_parent():
    acc = AccountName("ROOT:SUB")
    assert acc.name == "SUB"
    assert acc.parent is not None and acc.parent.full_name == "ROOT"
    with pytest.raises(DomainError):
        AccountName(":bad:")
    with pytest.raises(DomainError):
        AccountName("bad::bad")


def test_exchange_rate_and_entry_line():
    rate = ExchangeRate.from_number(1.234567)
    assert float(rate.value) > 0
    with pytest.raises(DomainError):
        ExchangeRate.from_number(0)
    line = EntryLine.create(EntrySide.DEBIT, "ROOT", 100, "USD", rate)
    assert line.amount == Decimal("100")
    with pytest.raises(DomainError):
        EntryLine.create(EntrySide.CREDIT, "ROOT", 0, "USD")


def test_transaction_balancing():
    debit = EntryLine.create(EntrySide.DEBIT, "ROOT", 100, "USD")
    credit = EntryLine.create(EntrySide.CREDIT, "ROOT", 100, "USD")
    tx = TransactionVO.from_lines([debit, credit])
    assert tx.debit_lines and tx.credit_lines
    # imbalance
    bad_credit = EntryLine.create(EntrySide.CREDIT, "ROOT", 99, "USD")
    with pytest.raises(DomainError):
        TransactionVO.from_lines([debit, bad_credit])

