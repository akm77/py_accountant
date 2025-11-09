from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from application.dto.models import CurrencyDTO, EntryLineDTO, RateUpdateInput
from application.use_cases.exchange_rates import UpdateExchangeRates
from application.use_cases.ledger import (
    CreateAccount,
    CreateCurrency,
    GetBalance,
    GetLedger,
    GetTradingBalance,
    PostTransaction,
)
from domain import DomainError, ExchangeRatePolicy
from infrastructure.persistence.inmemory.clock import FixedClock
from infrastructure.persistence.inmemory.uow import InMemoryUnitOfWork


def setup_uow() -> InMemoryUnitOfWork:
    return InMemoryUnitOfWork()


def test_create_currency_and_account():
    uow = setup_uow()
    create_currency = CreateCurrency(uow)
    usd = create_currency("usd")
    assert usd.code == "USD"
    create_account = CreateAccount(uow)
    acc = create_account("Assets:Cash", "USD")
    assert acc.full_name == "Assets:Cash"
    # duplicate account
    try:
        create_account("Assets:Cash", "USD")
        assert False, "Expected DomainError for duplicate"
    except DomainError:
        pass


def test_post_transaction_and_balance_and_ledger():
    uow = setup_uow()
    CreateCurrency(uow)("USD")
    CreateAccount(uow)("Assets:Cash", "USD")
    CreateAccount(uow)("Income:Sales", "USD")
    clock = FixedClock(fixed=datetime.now(UTC))
    post_tx = PostTransaction(uow, clock)
    line1 = EntryLineDTO(side="DEBIT", account_full_name="Assets:Cash", amount=Decimal("100.00"), currency_code="USD")
    line2 = EntryLineDTO(side="CREDIT", account_full_name="Income:Sales", amount=Decimal("100.00"), currency_code="USD")
    post_tx([line1, line2], memo="Sale")
    balance_uc = GetBalance(uow, clock)
    bal_cash = balance_uc("Assets:Cash")
    assert bal_cash == Decimal("100.00")
    bal_income = balance_uc("Income:Sales")
    assert bal_income == Decimal("-100.00")
    ledger_uc = GetLedger(uow, clock)
    led = ledger_uc("Assets:Cash")
    assert len(led) == 1 and led[0].lines[0].account_full_name == "Assets:Cash"


def test_trading_balance_use_case_with_rates():
    uow = setup_uow()
    # Base currency USD
    CreateCurrency(uow)("USD", exchange_rate=Decimal("1"))
    CreateCurrency(uow)("EUR", exchange_rate=Decimal("1.2"))  # 1 EUR = 1.2 USD
    CreateAccount(uow)("Assets:Cash", "USD")
    CreateAccount(uow)("Assets:BankEUR", "EUR")
    CreateAccount(uow)("Income:Sales", "USD")
    clock = FixedClock(fixed=datetime.now(UTC))
    post_tx = PostTransaction(uow, clock)
    # USD sale 120 USD
    post_tx([
        EntryLineDTO(side="DEBIT", account_full_name="Assets:Cash", amount=Decimal("120"), currency_code="USD"),
        EntryLineDTO(side="CREDIT", account_full_name="Income:Sales", amount=Decimal("120"), currency_code="USD"),
    ])
    # EUR sale 100 EUR (equivalent 120 USD). Use explicit rate lines (simulate captured rate) by setting exchange_rate.
    post_tx([
        EntryLineDTO(side="DEBIT", account_full_name="Assets:BankEUR", amount=Decimal("100"), currency_code="EUR", exchange_rate=Decimal("1.2")),
        EntryLineDTO(side="CREDIT", account_full_name="Income:Sales", amount=Decimal("100"), currency_code="EUR", exchange_rate=Decimal("1.2")),
    ])
    tb_uc = GetTradingBalance(uow, clock)
    tb = tb_uc(base_currency="USD")
    # Find EUR line and ensure raw debit recorded as 100 EUR
    eur_line = next(l for l in tb.lines if l.currency_code == "EUR")
    assert eur_line.total_debit == Decimal("100")


def test_update_exchange_rates_basic():
    uow = InMemoryUnitOfWork()
    # Seed currencies with proper DTOs
    uow.currencies.upsert(CurrencyDTO(code="USD"))
    uow.currencies.upsert(CurrencyDTO(code="EUR"))
    updater = UpdateExchangeRates(uow)
    updater([RateUpdateInput(code="EUR", rate=Decimal("1.1000000000"))], set_base="USD")
    eur = uow.currencies.get_by_code("EUR")
    usd = uow.currencies.get_by_code("USD")
    assert usd and usd.is_base is True
    assert eur and eur.exchange_rate is not None


def test_update_exchange_rates_policy_applied():
    uow = InMemoryUnitOfWork()
    uow.currencies.upsert(CurrencyDTO(code="USD"))
    uow.currencies.set_base("USD")
    uow.currencies.upsert(CurrencyDTO(code="GBP"))
    updater = UpdateExchangeRates(uow, policy=ExchangeRatePolicy(mode="weighted_average"))
    updater([RateUpdateInput(code="GBP", rate=Decimal("1.2000"))])
    # second update to average 1.2000 and 1.3000 -> 1.2500
    updater([RateUpdateInput(code="GBP", rate=Decimal("1.3000"))])
    gbp = uow.currencies.get_by_code("GBP")
    assert gbp and gbp.exchange_rate == Decimal("1.2500000000")


def test_set_base_currency_enforces_singleton():
    uow = InMemoryUnitOfWork()
    uow.currencies.upsert(CurrencyDTO(code="USD"))
    uow.currencies.upsert(CurrencyDTO(code="EUR"))
    uow.currencies.set_base("USD")
    uow.currencies.set_base("EUR")
    usd = uow.currencies.get_by_code("USD")
    eur = uow.currencies.get_by_code("EUR")
    assert eur and eur.is_base is True
    assert usd and usd.is_base is False


def test_get_trading_balance_infers_base_when_missing():
    uow = InMemoryUnitOfWork()
    uow.currencies.upsert(CurrencyDTO(code="USD"))
    uow.currencies.set_base("USD")
    from application.use_cases.ledger import CreateAccount, CreateCurrency, PostTransaction
    CreateCurrency(uow)("USD", exchange_rate=Decimal("1"))
    CreateAccount(uow)("Assets:Cash", "USD")
    CreateAccount(uow)("Income:Sales", "USD")
    clock = FixedClock(datetime.now(UTC))
    post = PostTransaction(uow, clock)
    post([EntryLineDTO(side="DEBIT", account_full_name="Assets:Cash", amount=Decimal("10"), currency_code="USD"), EntryLineDTO(side="CREDIT", account_full_name="Income:Sales", amount=Decimal("10"), currency_code="USD")])
    gb = GetTradingBalance(uow, clock)()
    assert gb.base_currency == "USD"
    # Since debits and credits in USD cancel out, base_total is 0.00
    assert gb.base_total == Decimal("0.00")
    assert gb.base_total == sum((l.converted_balance or Decimal("0")) for l in gb.lines)


def test_rounding_money_and_rates():
    uow = InMemoryUnitOfWork()
    uow.currencies.upsert(CurrencyDTO(code="USD"))
    uow.currencies.set_base("USD")
    uow.currencies.upsert(CurrencyDTO(code="JPY"))
    updater = UpdateExchangeRates(uow)
    updater([RateUpdateInput(code="JPY", rate=Decimal("150.1234567890"))])
    from application.use_cases.ledger import CreateAccount, CreateCurrency, PostTransaction
    CreateCurrency(uow)("USD", exchange_rate=Decimal("1"))
    CreateCurrency(uow)("JPY", exchange_rate=Decimal("150.1234567890"))
    CreateAccount(uow)("Assets:CashUSD", "USD")
    CreateAccount(uow)("Assets:CashJPY", "JPY")
    clock = FixedClock(datetime.now(UTC))
    post = PostTransaction(uow, clock)
    # Balance amounts in base: credit JPY amount * (1 / rate) should equal debit USD 100 -> credit JPY = 100 * rate
    post([
        EntryLineDTO(side="DEBIT", account_full_name="Assets:CashUSD", amount=Decimal("100"), currency_code="USD"),
        EntryLineDTO(side="CREDIT", account_full_name="Assets:CashJPY", amount=Decimal("15012.34567890"), currency_code="JPY", exchange_rate=Decimal("150.1234567890")),
    ])
    gb = GetTradingBalance(uow, clock)(base_currency="USD")
    assert gb.base_total == gb.lines[0].converted_balance + gb.lines[1].converted_balance
    assert all(str(l.converted_balance).count('.') <= 1 and len(str(l.converted_balance).split('.')[-1]) <= 2 for l in gb.lines)
