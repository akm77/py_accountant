"""Diagnostics helpers for parity reporting between legacy Book and new use cases.

The parity report executes predefined or user-supplied scenarios against both engines:
- Legacy Book (if available)
- In-memory UnitOfWork + use cases

If legacy is not importable, report marks all scenarios as 'skipped' with reason.
This module is intentionally lightweight and avoids new external dependencies.
"""
from __future__ import annotations

import importlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from application.dto.models import EntryLineDTO
from application.use_cases.ledger import (
    CreateAccount,
    CreateCurrency,
    GetBalance,
    GetTradingBalanceDetailed,
    PostTransaction,
)
from application.utils.quantize import money_quantize
from domain.services.exchange_rate_policy import ExchangeRatePolicy
from domain.value_objects import DomainError
from infrastructure.persistence.inmemory.clock import FixedClock
from infrastructure.persistence.inmemory.uow import InMemoryUnitOfWork


# Scenario definition (simple dataclass for readability)
@dataclass(slots=True)
class Scenario:
    name: str
    lines: list[tuple[str, str, Decimal, str, Decimal | None, dict | None]]
    # Optional expected invariants (for future extensions)
    expect_accounts: list[str] | None = None


def _default_scenarios() -> list[Scenario]:
    return [
        Scenario(
            name="single_currency_basic",
            lines=[
                ("DEBIT", "Assets:Cash", Decimal("100"), "USD", Decimal("1"), None),
                ("CREDIT", "Income:Sales", Decimal("100"), "USD", Decimal("1"), None),
            ],
        ),
        Scenario(
            name="multi_currency_cross",
            lines=[
                ("DEBIT", "Assets:Cash", Decimal("100"), "USD", Decimal("1"), None),
                ("CREDIT", "Income:Sales", Decimal("125"), "EUR", Decimal("1.25"), None),
            ],
        ),
        Scenario(
            name="rounding_edge",
            lines=[
                ("DEBIT", "Assets:Cash", Decimal("0.005"), "USD", Decimal("1"), None),
                ("CREDIT", "Income:Sales", Decimal("0.005"), "USD", Decimal("1"), None),
            ],
        ),
    ]


def _load_scenarios_from_file(path: str) -> list[Scenario]:
    raw = json.loads(open(path, encoding="utf-8").read())
    if not isinstance(raw, list):
        raise DomainError("Scenarios JSON must be a list")
    scenarios: list[Scenario] = []
    for item in raw:
        if not isinstance(item, dict):
            raise DomainError("Scenario item must be object")
        name = str(item.get("name", "unnamed"))
        raw_lines = item.get("lines")
        if not isinstance(raw_lines, list) or not raw_lines:
            raise DomainError(f"Scenario {name} has invalid lines")
        lines: list[tuple[str, str, Decimal, str, Decimal | None, dict | None]] = []
        for ln in raw_lines:
            if not isinstance(ln, dict):
                raise DomainError("Line must be object")
            side = str(ln.get("side"))
            account = str(ln.get("account"))
            amount = Decimal(str(ln.get("amount")))
            currency = str(ln.get("currency"))
            rate_raw = ln.get("rate")
            rate = Decimal(str(rate_raw)) if rate_raw is not None else None
            meta = ln.get("meta") if isinstance(ln.get("meta"), dict) else None
            lines.append((side, account, amount, currency, rate, meta))
        scenarios.append(Scenario(name=name, lines=lines))
    return scenarios


def _setup_legacy(test_db_url: str) -> Any:
    try:
        legacy_mod = importlib.import_module("py_fledger.book")
    except Exception as exc:
        raise DomainError("Legacy Book not importable") from exc
    legacy_book = getattr(legacy_mod, "Book", None)
    if legacy_book is None:
        raise DomainError("Legacy Book class missing")
    lb = legacy_book(test_db_url)
    lb.init()
    return lb


def _post_legacy(lb: Any, memo: str, lines: list[tuple[str, str, Decimal, str, Decimal | None, dict | None]]):
    e = lb.entry(memo)
    for side, account, amount, currency, rate, meta in lines:
        _ = currency
        if side.upper() == "DEBIT":
            e.debit(account, float(amount), meta or {}, float(rate) if rate else None)
        else:
            e.credit(account, float(amount), meta or {}, float(rate) if rate else None)
    e.commit()


def _post_new(uow: InMemoryUnitOfWork, clock: FixedClock, memo: str, lines: list[tuple[str, str, Decimal, str, Decimal | None, dict | None]]):
    dto_lines: list[EntryLineDTO] = []
    for side, account, amount, currency, rate, meta in lines:
        dto_lines.append(
            EntryLineDTO(
                side=side.upper(),
                account_full_name=account,
                amount=amount,
                currency_code=currency.upper(),
                exchange_rate=rate,
                meta=meta or {},
            )
        )
    policy = ExchangeRatePolicy(mode="last_write")
    PostTransaction(uow, clock, rate_policy=policy)(dto_lines, memo=memo, meta={})


def run_parity_report(*, preset: str = "default", scenarios_path: str | None, tolerance: Decimal) -> dict[str, Any]:
    # Prepare scenarios
    if scenarios_path:
        scenarios = _load_scenarios_from_file(scenarios_path)
    else:
        scenarios = _default_scenarios() if preset == "default" else _default_scenarios()
    report: dict[str, Any] = {"scenarios": [], "summary": {"total": 0, "matched": 0, "diverged": 0}}

    # Attempt legacy setup
    legacy_available = True
    try:
        lb = _setup_legacy("sqlite+pysqlite:///:memory:")
    except Exception:
        legacy_available = False
        lb = None

    now = datetime.now(UTC)
    for sc in scenarios:
        result: dict[str, Any] = {"name": sc.name, "status": "skipped", "differences": {}, "tolerance": str(tolerance)}
        if not legacy_available:
            result["status"] = "skipped"
            result["reason"] = "legacy_unavailable"
            report["scenarios"].append(result)
            continue
        # Setup new engine per scenario for isolation
        uow = InMemoryUnitOfWork()
        clock = FixedClock(now)
        # Baseline currencies inferred from lines
        cur_codes = sorted({ln[3].upper() for ln in sc.lines})
        for code in cur_codes:
            CreateCurrency(uow)(code)
        # Set first currency as base for deterministic parity if only one currency
        base_cur = cur_codes[0] if cur_codes else None
        if base_cur:
            uow.currencies.set_base(base_cur)
        # Accounts inferred from lines
        accs = sorted({ln[1] for ln in sc.lines})
        # Map account -> currency from scenario lines (first match wins)
        acc_currency: dict[str, str] = {}
        for side, account, amount, currency, rate, meta in sc.lines:
            acc_currency.setdefault(account, currency.upper())
        for acc in accs:
            line_currency = acc_currency.get(acc, base_cur or (cur_codes[0] if cur_codes else "USD"))
            CreateAccount(uow)(acc, line_currency)
        # Legacy parallel setup
        # currencies
        for code in cur_codes:
            try:
                lb.create_currency(code)
            except Exception:
                pass
        # accounts (legacy requires parent chains). Parents use base currency; leaf uses its own.
        for acc in accs:
            parts = acc.split(":")
            leaf_currency = acc_currency.get(acc, base_cur or (cur_codes[0] if cur_codes else parts[-1]))
            chain = []
            for i in range(1, len(parts) + 1):
                chain.append(":".join(parts[:i]))
            for name in chain:
                cur_for_node = leaf_currency if name == acc else (base_cur or leaf_currency)
                try:
                    lb.create_account(name, cur_for_node)
                except Exception:
                    # ignore if already exists or any benign error
                    pass
        # Post transactions
        try:
            _post_legacy(lb, sc.name, sc.lines)
        except Exception as exc:
            result["status"] = "diverged"
            result["reason"] = f"legacy_error:{exc}"
            result["differences"] = {"error": "legacy_post_failed"}
            report["scenarios"].append(result)
            continue
        _post_new(uow, clock, sc.name, sc.lines)
        # Collect parity data
        differences: dict[str, Any] = {"balances": {}, "trading_balance": {}, "transactions": {}, "rounding_deltas": []}
        matched = True
        # Balances per account with quantization
        for acc in accs:
            try:
                legacy_bal = Decimal(str(int(lb.balance(acc))))
            except Exception:
                legacy_bal = Decimal("0")
            new_bal = GetBalance(uow, clock)(acc)
            q_legacy = money_quantize(legacy_bal)
            q_new = money_quantize(new_bal)
            delta = (q_legacy - q_new).copy_abs()
            if delta > tolerance:
                matched = False
                differences["rounding_deltas"].append({"account": acc, "legacy": str(q_legacy), "new": str(q_new), "delta": str(delta)})
            differences["balances"][acc] = {"legacy": str(q_legacy), "new": str(q_new), "delta": str(delta)}
        # Trading balance detailed parity
        base_code = base_cur
        if base_code:
            tb_new = GetTradingBalanceDetailed(uow, clock)(base_code)
            try:
                tb_leg = lb.trading_balance()
                legacy_base_total = Decimal(str(int(tb_leg.get("base", 0))))
            except Exception:
                legacy_base_total = Decimal("0")
            q_legacy_total = money_quantize(legacy_base_total)
            q_new_total = money_quantize(tb_new.base_total or Decimal("0"))
            tb_delta = (q_legacy_total - q_new_total).copy_abs()
            if tb_delta > tolerance:
                matched = False
                differences["rounding_deltas"].append({"trading_base_total": True, "legacy": str(q_legacy_total), "new": str(q_new_total), "delta": str(tb_delta)})
            differences["trading_balance"] = {"base_total": {"legacy": str(q_legacy_total), "new": str(q_new_total), "delta": str(tb_delta)}}
            # Detailed per-currency lines (new engine only, legacy has aggregate). Provide converted_balance parity info.
            cur_lines = {}
            for line in tb_new.lines:
                cur_lines[line.currency_code] = {
                    "balance": str(money_quantize(line.balance)),
                    "converted_balance": str(money_quantize(line.converted_balance or Decimal("0"))),
                    "rate_used": str(line.rate_used) if line.rate_used is not None else None,
                    "fallback": line.rate_fallback,
                }
            differences["trading_balance"]["lines"] = cur_lines
        # Transaction counts heuristic
        try:
            legacy_tx_count = len(lb.ledger(accs[0])) if accs else 0
        except Exception:
            legacy_tx_count = 0
        new_tx_count = 1
        if legacy_tx_count < 1:
            matched = False
        differences["transactions"] = {"count": {"legacy": legacy_tx_count, "new": new_tx_count}}
        result["status"] = "matched" if matched else "diverged"
        result["differences"] = differences
        report["scenarios"].append(result)
    total = len(report["scenarios"])
    matched = sum(1 for s in report["scenarios"] if s["status"] == "matched")
    diverged = sum(1 for s in report["scenarios"] if s["status"] == "diverged")
    report["summary"] = {"total": total, "matched": matched, "diverged": diverged}
    return report
