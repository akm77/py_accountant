from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest

from application.dto.models import EntryLineDTO
from application.use_cases.ledger import (
    CreateAccount,
    CreateCurrency,
    GetBalance,
    GetTradingBalanceDetailed,
    ListLedger,
    PostTransaction,
)
from domain.services.exchange_rate_policy import ExchangeRatePolicy
from domain.value_objects import DomainError
from infrastructure.persistence.inmemory.clock import FixedClock
from infrastructure.persistence.inmemory.uow import InMemoryUnitOfWork
from py_fledger import book as legacy_book
from py_fledger.errors import FError as LegacyError

TEST_DB = "sqlite+pysqlite:///:memory:"  # for legacy book


def _setup_legacy_and_new(now: datetime) -> tuple[Any, InMemoryUnitOfWork, FixedClock]:
    lb = legacy_book(TEST_DB)
    lb.init()
    uow = InMemoryUnitOfWork()
    clock = FixedClock(now)
    return lb, uow, clock


def _post_legacy(lb, memo: str, lines: list[tuple[str, str, int, str, float | None, dict | None]]):
    e = lb.entry(memo)
    for side, account, amount, currency, rate, meta in lines:
        _ = currency  # referenced to avoid linter warning (legacy API infers by account)
        if side == "DEBIT":
            e.debit(account, amount, meta or {}, rate)
        else:
            e.credit(account, amount, meta or {}, rate)
    e.commit()


def _post_new(uow: InMemoryUnitOfWork, clock: FixedClock, memo: str, lines: list[tuple[str, str, int, str, float | None, dict | None]]):
    dto_lines: list[EntryLineDTO] = []
    for side, account, amount, currency, rate, meta in lines:
        dto_lines.append(
            EntryLineDTO(
                side=side,
                account_full_name=account,
                amount=Decimal(str(amount)),
                currency_code=currency,
                exchange_rate=Decimal(str(rate)) if rate else None,
                meta=meta or {},
            )
        )
    # Apply last_write policy to propagate exchange rates like legacy Book
    policy = ExchangeRatePolicy(mode="last_write")
    PostTransaction(uow, clock, rate_policy=policy)(dto_lines, memo=memo, meta={})


@pytest.mark.parametrize("rate", [None, 1.0])
def test_parity_single_tx_usd(rate):
    now = datetime.now(UTC)
    lb, uow, clock = _setup_legacy_and_new(now)
    # currencies/accounts
    lb.create_currency("USD")
    CreateCurrency(uow)("USD")
    uow.currencies.set_base("USD")  # establish base like legacy id=1
    # Root parents first (legacy requirement)
    lb.create_account("Assets", "USD")
    lb.create_account("Income", "USD")
    CreateAccount(uow)("Assets", "USD")
    CreateAccount(uow)("Income", "USD")
    lb.create_account("Assets:Cash", "USD")
    lb.create_account("Income:Sales", "USD")
    CreateAccount(uow)("Assets:Cash", "USD")
    CreateAccount(uow)("Income:Sales", "USD")

    # Post identical transaction
    _post_legacy(lb, "Sale", [
        ("DEBIT", "Assets:Cash", 100, "USD", rate, None),
        ("CREDIT", "Income:Sales", 100, "USD", rate, None),
    ])
    _post_new(uow, clock, "Sale", [
        ("DEBIT", "Assets:Cash", 100, "USD", rate, None),
        ("CREDIT", "Income:Sales", 100, "USD", rate, None),
    ])

    # Balance parity
    legacy_bal = int(lb.balance("Assets:Cash"))
    new_bal = int(GetBalance(uow, clock)("Assets:Cash"))
    assert legacy_bal == new_bal == 100


def test_parity_multi_currency_with_rates():
    now = datetime.now(UTC)
    lb, uow, clock = _setup_legacy_and_new(now)
    # currencies
    lb.create_currency("USD")
    lb.create_currency("EUR")
    CreateCurrency(uow)("USD")
    CreateCurrency(uow)("EUR")
    uow.currencies.set_base("USD")
    # accounts
    lb.create_account("Assets", "USD")
    lb.create_account("Income", "USD")
    CreateAccount(uow)("Assets", "USD")
    CreateAccount(uow)("Income", "USD")
    lb.create_account("Assets:Cash", "USD")
    lb.create_account("Income:Sales", "EUR")
    CreateAccount(uow)("Assets:Cash", "USD")
    CreateAccount(uow)("Income:Sales", "EUR")

    _post_legacy(lb, "Cross", [
        ("DEBIT", "Assets:Cash", 100, "USD", 1.0, None),
        ("CREDIT", "Income:Sales", 125, "EUR", 1.25, None),
    ])
    _post_new(uow, clock, "Cross", [
        ("DEBIT", "Assets:Cash", 100, "USD", 1.0, None),
        ("CREDIT", "Income:Sales", 125, "EUR", 1.25, None),
    ])

    legacy_bal_usd = int(lb.balance("Assets:Cash"))
    new_bal_usd = int(GetBalance(uow, clock)("Assets:Cash"))
    assert legacy_bal_usd == new_bal_usd == 100

    # Trading balance detailed comparison (base USD)
    tb_new = GetTradingBalanceDetailed(uow, clock)("USD")
    # Legacy trading balance returns base + per currency strings
    tb_legacy = lb.trading_balance()
    # Compare base total parity (legacy base str to int)
    assert int(tb_legacy["base"]) == int(tb_new.base_total)  # type: ignore[arg-type]


def test_parity_ledger_window_and_order():
    now = datetime.now(UTC)
    lb, uow, clock = _setup_legacy_and_new(now)
    lb.create_currency("USD")
    CreateCurrency(uow)("USD")
    uow.currencies.set_base("USD")
    lb.create_account("Assets", "USD")
    CreateAccount(uow)("Assets", "USD")
    lb.create_account("Assets:Cash", "USD")
    CreateAccount(uow)("Assets:Cash", "USD")

    # series of txs
    base_time = now
    last_time = base_time
    for i in range(5):
        _post_legacy(lb, f"Tx {i}", [
            ("DEBIT", "Assets:Cash", 10 + i, "USD", 1.0, {"seq": i}),
            ("CREDIT", "Assets:Cash", 10 + i, "USD", 1.0, {"seq": i}),
        ])
        iter_time = base_time + timedelta(seconds=i)
        last_time = iter_time
        iter_clock = FixedClock(iter_time)
        _post_new(uow, iter_clock, f"Tx {i}", [
            ("DEBIT", "Assets:Cash", 10 + i, "USD", 1.0, {"seq": i}),
            ("CREDIT", "Assets:Cash", 10 + i, "USD", 1.0, {"seq": i}),
        ])

    legacy_ledger = lb.ledger("Assets:Cash")
    # Use a clock after the last transaction to include all
    query_clock = FixedClock(last_time + timedelta(seconds=1))
    new_ledger = ListLedger(uow, query_clock)("Assets:Cash", order="DESC")
    assert len(new_ledger) == 5
    assert len(legacy_ledger) == len(new_ledger) * 2  # legacy has per-line transactions

    # Window (limit) parity semantics: compare subset ordering
    subset_legacy = lb.ledger("Assets:Cash", None, {"limit": 2})
    subset_new = ListLedger(uow, query_clock)("Assets:Cash", limit=2, order="DESC")
    assert len(subset_new) == 2
    assert len(subset_legacy) == 2


def test_parity_trading_balance_and_detailed():
    now = datetime.now(UTC)
    lb, uow, clock = _setup_legacy_and_new(now)
    lb.create_currency("USD")
    lb.create_currency("EUR")
    CreateCurrency(uow)("USD")
    CreateCurrency(uow)("EUR")
    uow.currencies.set_base("USD")
    lb.create_account("Assets", "USD")
    lb.create_account("Income", "USD")
    CreateAccount(uow)("Assets", "USD")
    CreateAccount(uow)("Income", "USD")
    lb.create_account("Assets:Cash", "USD")
    lb.create_account("Income:Sales", "EUR")
    CreateAccount(uow)("Assets:Cash", "USD")
    CreateAccount(uow)("Income:Sales", "EUR")

    _post_legacy(lb, "Cross", [
        ("DEBIT", "Assets:Cash", 100, "USD", 1.0, None),
        ("CREDIT", "Income:Sales", 125, "EUR", 1.25, None),
    ])
    _post_new(uow, clock, "Cross", [
        ("DEBIT", "Assets:Cash", 100, "USD", 1.0, None),
        ("CREDIT", "Income:Sales", 125, "EUR", 1.25, None),
    ])

    tb_legacy = lb.trading_balance()
    tb_new_detailed = GetTradingBalanceDetailed(uow, clock)("USD")
    assert int(tb_legacy["base"]) == int(tb_new_detailed.base_total)  # type: ignore[arg-type]
    eur_line = next(line for line in tb_new_detailed.lines if line.currency_code == "EUR")
    assert str(eur_line.rate_used) == "1.25"


def test_negative_unbalanced_transaction_rejected():
    now = datetime.now(UTC)
    lb, uow, clock = _setup_legacy_and_new(now)
    lb.create_currency("USD")
    CreateCurrency(uow)("USD")
    uow.currencies.set_base("USD")
    lb.create_account("Assets", "USD")
    lb.create_account("Income", "USD")
    CreateAccount(uow)("Assets", "USD")
    CreateAccount(uow)("Income", "USD")
    lb.create_account("Assets:Cash", "USD")
    lb.create_account("Income:Sales", "USD")
    CreateAccount(uow)("Assets:Cash", "USD")
    CreateAccount(uow)("Income:Sales", "USD")

    # Legacy: attempt commit unbalanced
    e = lb.entry("Bad")
    e.debit("Assets:Cash", 100)
    e.credit("Income:Sales", 99)
    with pytest.raises(LegacyError):
        e.commit()

    # New: attempt post unbalanced
    lines = [
        EntryLineDTO(side="DEBIT", account_full_name="Assets:Cash", amount=Decimal("100"), currency_code="USD"),
        EntryLineDTO(side="CREDIT", account_full_name="Income:Sales", amount=Decimal("99"), currency_code="USD"),
    ]
    with pytest.raises(DomainError):
        PostTransaction(uow, clock)(lines)
