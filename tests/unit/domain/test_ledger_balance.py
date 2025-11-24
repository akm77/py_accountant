from decimal import Decimal, getcontext

import pytest

from py_accountant.domain.currencies import Currency
from py_accountant.domain.errors import DomainError, ValidationError
from py_accountant.domain.ledger import EntrySide, LedgerEntry, LedgerValidator


def make_currencies_usd_eur_jpy():
    usd = Currency(code="USD", is_base=True)
    eur = Currency(code="EUR")
    eur.set_rate(Decimal("1.2"))
    jpy = Currency(code="JPY")
    jpy.set_rate(Decimal("0.009"))
    return [usd, eur, jpy]


def test_single_currency_balanced():
    currencies = [Currency(code="USD", is_base=True)]
    lines = [
        LedgerEntry(side=EntrySide.DEBIT, amount=100, currency_code="USD"),
        LedgerEntry(side="credit", amount="100", currency_code="usd"),
    ]
    LedgerValidator.validate(lines, currencies)


def test_multi_currency_balanced_with_rates():
    currencies = make_currencies_usd_eur_jpy()
    # Example 1: 50 EUR debit vs 60 USD credit (EUR->USD 1.2)
    lines1 = [
        LedgerEntry(side="debit", amount=50, currency_code="EUR"),
        LedgerEntry(side="CREDIT", amount=60, currency_code="USD"),
    ]

    # Example 2: 10000 JPY debit vs 90 USD credit (JPY->USD 0.009)
    lines2 = [
        LedgerEntry(side=EntrySide.DEBIT, amount=10000, currency_code="jpy"),
        LedgerEntry(side=EntrySide.CREDIT, amount=90, currency_code="USD"),
    ]

    # Preserve global Decimal context
    prec_before = getcontext().prec
    rounding_before = getcontext().rounding

    LedgerValidator.validate(lines1, currencies)
    LedgerValidator.validate(lines2, currencies)

    assert getcontext().prec == prec_before
    assert getcontext().rounding == rounding_before


def test_unbalanced_detected():
    currencies = [Currency(code="USD", is_base=True), Currency(code="EUR")]
    # set rate EUR->USD = 1.2
    currencies[1].set_rate(Decimal("1.2"))

    lines = [
        LedgerEntry(side="DEBIT", amount=50, currency_code="EUR"),
        LedgerEntry(side="CREDIT", amount="59.99", currency_code="USD"),
    ]

    with pytest.raises(DomainError):
        LedgerValidator.validate(lines, currencies)


@pytest.mark.parametrize(
    "lines,currencies,base_code,exc",
    [
        # Empty lines
        ([], [Currency(code="USD", is_base=True)], None, ValidationError),
        # No base and not provided
        ([LedgerEntry("DEBIT", 1, "USD"), LedgerEntry("CREDIT", 1, "USD")], [Currency(code="USD")], None, ValidationError),
        # base_code invalid
        ([LedgerEntry("DEBIT", 1, "USD"), LedgerEntry("CREDIT", 1, "USD")], [Currency(code="USD", is_base=True)], "EUR", ValidationError),
        # unknown currency in line
        ([LedgerEntry("DEBIT", 1, "EUR"), LedgerEntry("CREDIT", 1, "EUR")], [Currency(code="USD", is_base=True)], None, ValidationError),
    ],
)
def test_negative_cases(lines, currencies, base_code, exc):
    with pytest.raises(exc):
        LedgerValidator.validate(lines, currencies, base_code)


@pytest.mark.parametrize(
    "line_maker",
    [
        lambda: LedgerEntry("DEBIT", 0, "USD"),
        lambda: LedgerEntry("DEBIT", -1, "USD"),
        lambda: LedgerEntry("XXX", 1, "USD"),
        lambda: LedgerEntry("DEBIT", 1, "US"),
        lambda: LedgerEntry("DEBIT", 1, "U" * 11),
    ],
)
def test_entry_validation(line_maker):
    with pytest.raises(ValidationError):
        _ = line_maker()


def test_non_base_currency_rate_required_and_positive():
    usd = Currency(code="USD", is_base=True)
    bad = Currency(code="EUR")
    lines = [
        LedgerEntry("DEBIT", 10, "EUR"),
        LedgerEntry("CREDIT", 10, "USD"),
    ]
    with pytest.raises(ValidationError):
        LedgerValidator.validate(lines, [usd, bad])

    # Non-positive rate
    bad2 = Currency(code="EUR")
    with pytest.raises(ValidationError):
        bad2.set_rate(Decimal("0"))

    bad3 = Currency(code="EUR")
    with pytest.raises(ValidationError):
        bad3.set_rate(Decimal("-0.1"))


def test_rounding_half_even_comparison():
    usd = Currency(code="USD", is_base=True)
    eur = Currency(code="EUR")
    eur.set_rate(Decimal("1.234567"))  # 6dp rate
    # amount 10 EUR -> 12.34567 USD; money_quantize -> 12.35
    lines = [
        LedgerEntry("DEBIT", Decimal("10"), "EUR"),
        LedgerEntry("CREDIT", Decimal("12.35"), "USD"),
    ]
    LedgerValidator.validate(lines, [usd, eur])
