"""Diagnostics helpers for parity reporting without legacy engine.

The parity report runs predefined or user-supplied scenarios only against the new
use cases (in-memory UnitOfWork). If an expected-file is provided, it validates
internal consistency against that reference. Otherwise scenarios are marked as
"skipped" with reason "legacy_unavailable" to preserve output stability.

No imports or runtime checks for legacy modules remain.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from application.dto.models import EntryLineDTO
from application.use_cases.ledger import (
    CreateAccount,
    CreateCurrency,
    GetBalance,
    GetTradingBalanceRawDTOs,
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
    with open(path, encoding="utf-8") as fh:
        raw = json.loads(fh.read())
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


def run_parity_report(*, preset: str = "default", scenarios_path: str | None, expected_path: str | None = None, tolerance: Decimal) -> dict[str, Any]:
    # Prepare scenarios
    if scenarios_path:
        scenarios = _load_scenarios_from_file(scenarios_path)
    else:
        scenarios = _default_scenarios() if preset == "default" else _default_scenarios()
    expected_map: dict[str, Any] = {}
    if expected_path and os.path.exists(expected_path):  # type: ignore[name-defined]
        try:
            with open(expected_path, encoding="utf-8") as fh:
                raw_expected = json.loads(fh.read())
            if isinstance(raw_expected, dict):
                expected_map = raw_expected
        except Exception:
            expected_map = {}
    report: dict[str, Any] = {"scenarios": [], "summary": {"total": 0, "matched": 0, "diverged": 0}}
    now = datetime.now(UTC)
    for sc in scenarios:
        result: dict[str, Any] = {"name": sc.name, "status": "skipped", "differences": {}, "tolerance": str(tolerance)}
        if not expected_map:
            result["status"] = "skipped"
            result["reason"] = "legacy_unavailable"
            report["scenarios"].append(result)
            continue
        # Build new engine state
        uow = InMemoryUnitOfWork()
        clock = FixedClock(now)
        cur_codes = sorted({ln[3].upper() for ln in sc.lines})
        for code in cur_codes:
            CreateCurrency(uow)(code)
        base_cur = cur_codes[0] if cur_codes else None
        if base_cur:
            uow.currencies.set_base(base_cur)
        accs = sorted({ln[1] for ln in sc.lines})
        acc_currency: dict[str, str] = {}
        for _, account, _, currency, _, _ in sc.lines:
            acc_currency.setdefault(account, currency.upper())
        for acc in accs:
            line_currency = acc_currency.get(acc, base_cur or (cur_codes[0] if cur_codes else "USD"))
            CreateAccount(uow)(acc, line_currency)
        _post_new(uow, clock, sc.name, sc.lines)
        # Compare vs expected
        differences: dict[str, Any] = {"balances": {}, "trading_balance": {}, "rounding_deltas": []}
        matched = True
        expected_entry = expected_map.get(sc.name, {}) if isinstance(expected_map.get(sc.name, {}), dict) else {}
        expected_balances: dict[str, str] = expected_entry.get("balances", {}) if isinstance(expected_entry.get("balances", {}), dict) else {}
        for acc in accs:
            new_bal = GetBalance(uow, clock)(acc)
            q_new = money_quantize(new_bal)
            exp_val = Decimal(str(expected_balances.get(acc, "0")))
            q_exp = money_quantize(exp_val)
            delta = (q_exp - q_new).copy_abs()
            if delta > tolerance:
                matched = False
                differences["rounding_deltas"].append({"account": acc, "expected": str(q_exp), "new": str(q_new), "delta": str(delta)})
            differences["balances"][acc] = {"expected": str(q_exp), "new": str(q_new), "delta": str(delta)}
        exp_base_total = Decimal(str(expected_entry.get("base_total", "0")))
        raw_lines = GetTradingBalanceRawDTOs(uow, clock)()
        # When comparing with expected, assume base currency is first of scenario list or USD fallback
        base_code = base_cur or (cur_codes[0] if cur_codes else "USD")
        # Build currency->rate map from repository (None for base treated as 1)
        repo_curs = {c.code: c for c in uow.currencies.list_all()}
        new_base_total = Decimal("0")
        for l in raw_lines:
            rate = repo_curs.get(l.currency_code).exchange_rate if repo_curs.get(l.currency_code) else Decimal("1")
            used = Decimal("1") if l.currency_code == base_code else rate or Decimal("1")
            new_base_total += (l.debit - l.credit) * used
        new_base_total = money_quantize(new_base_total)
        delta_bt = (money_quantize(exp_base_total) - new_base_total).copy_abs()
        if delta_bt > tolerance:
            matched = False
            differences["rounding_deltas"].append({"trading_base_total": True, "expected": str(money_quantize(exp_base_total)), "new": str(new_base_total), "delta": str(delta_bt)})
        differences["trading_balance"] = {"base_total": {"expected": str(money_quantize(exp_base_total)), "new": str(new_base_total), "delta": str(delta_bt)}}
        result["status"] = "matched" if matched else "diverged"
        result["differences"] = differences
        report["scenarios"].append(result)
    total = len(report["scenarios"])
    matched = sum(1 for s in report["scenarios"] if s["status"] == "matched")
    diverged = sum(1 for s in report["scenarios"] if s["status"] == "diverged")
    report["summary"] = {"total": total, "matched": matched, "diverged": diverged}
    return report
