from __future__ import annotations

import argparse
import inspect
import json
import os
import sys
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from application.dto.models import EntryLineDTO
from application.utils.quantize import money_quantize
from domain.services.exchange_rate_policy import ExchangeRatePolicy
from domain.value_objects import DomainError
from infrastructure.logging.config import configure_logging, get_logger
from infrastructure.persistence.inmemory.uow import InMemoryUnitOfWork as MemUoW
from presentation.async_bridge import (
    bulk_upsert_rates_sync,
    create_account_sync,
    create_currency_sync,
    fx_ttl_apply_sync,
    get_account_balance_sync,
    get_currency_sync,
    get_ledger_sync,
    get_trading_balance_detailed_sync,
    get_trading_balance_sync,
    list_currencies_sync,
    list_exchange_rate_events_sync,
    post_transaction_sync,
    set_base_currency_sync,
    set_currency_rate_sync,
)
from presentation.cli import formatters

# Global state (simple) to persist in-memory UoW across CLI invocations in same process
_GLOBAL: dict[str, Any] = {}

# Lightweight in-process FX rate history (ephemeral). Key: currency code, Value: list of last N Decimal rates.
# N is controlled by env RATE_HISTORY_LEN (default=10).
try:
    from collections import deque
except Exception:  # pragma: no cover
    deque = list  # type: ignore

_RATES_HISTORY: dict[str, Any] = {}


def _rate_history_len() -> int:
    """Return configured history length (env RATE_HISTORY_LEN or default)."""
    try:
        return int(os.getenv("RATE_HISTORY_LEN", "10"))
    except Exception:
        return 10


def _history_append(code: str, rate: Decimal) -> None:
    """Append rate sample to in-memory history for currency code (bounded)."""
    code_up = code.upper()
    buf = _RATES_HISTORY.get(code_up)
    if buf is None:
        # Use deque with maxlen for bounded memory
        try:
            buf = deque(maxlen=_rate_history_len())  # type: ignore[call-arg]
        except Exception:
            buf = []
        _RATES_HISTORY[code_up] = buf
    try:
        buf.append(rate)  # type: ignore[attr-defined]
    except Exception:
        # fallback for list
        buf.append(rate)  # type: ignore[assignment]


def _history_snapshot(codes: list[str] | None = None, *, limit: int | None = None) -> list[dict[str, Any]]:
    """Return snapshot of recent rates for given codes (or all)."""
    result: list[dict[str, Any]] = []
    # Optionally ensure deterministic ordering by code
    codes_set = set(codes) if codes else None
    all_codes = sorted(_RATES_HISTORY.keys()) if _RATES_HISTORY else []
    for code in all_codes:
        if codes_set is not None and code not in codes_set:
            continue
        buf = _RATES_HISTORY.get(code) or []
        items = list(buf)
        if limit is not None and limit >= 0:
            items = items[-limit:] if limit > 0 else []
        result.append({"code": code, "rates": [str(x) for x in items], "count": len(items)})
    # Include currencies with no updates as empty arrays if specific codes requested
    if codes:
        for code in sorted(set(codes) - set(all_codes)):
            result.append({"code": code, "rates": [], "count": 0})
    return sorted(result, key=lambda x: x["code"])  # stable


def _get_mem_uow() -> MemUoW:
    """Return (and cache) in-memory UoW with per-test isolation.

    Isolation strategy:
    - If PYTEST_CURRENT_TEST env var present -> use it (explicit override).
    - Else, inspect call stack for first frame whose file path contains '/tests/' and
      build a key as '__mem__:<relative_file>:<function>'. This provides isolation
      between different test functions while allowing multiple CLI invocations
      within the same test to share state.
    - Fallback to '__mem__' if no test frame found (non-test runtime).
    """
    test_id = os.environ.get("PYTEST_CURRENT_TEST")
    key_base = "__mem__"
    if not test_id:
        try:
            frames = inspect.stack()  # pragma: no cover - stack introspection
            test_frames = [fr for fr in frames if "/tests/" in fr.filename]
            chosen = None
            for fr in reversed(test_frames):  # outermost first
                if fr.function.startswith("test"):
                    chosen = fr
                    break
            if chosen is None and test_frames:
                chosen = test_frames[-1]  # fallback to the outermost test file frame
            if chosen is not None:
                fname = os.path.relpath(chosen.filename)
                func = chosen.function
                test_id = f"{fname}:{func}"
        except Exception:
            test_id = None
    key = f"{key_base}:{test_id}" if test_id else key_base
    uow = _GLOBAL.get(key)
    if not uow:
        uow = MemUoW()
        _GLOBAL[key] = uow
    return uow


def _parse_iso8601(value: str | None) -> datetime | None:
    """Parse ISO8601 string to timezone-aware datetime (UTC if naive)."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except Exception as exc:  # noqa: PERF203
        raise DomainError(f"Invalid ISO8601 datetime: {value}") from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


def _parse_line(raw: str) -> EntryLineDTO:
    """Parse --line CLI argument into EntryLineDTO (supports optional rate)."""
    parts = raw.split(":")
    if len(parts) < 4:
        raise DomainError(f"Invalid --line format: {raw}")
    side = parts[0]
    rate: Decimal | None = None

    # Decide if the last token is a numeric rate
    def _is_decimal_token(s: str) -> bool:
        try:
            Decimal(str(s))
            return True
        except Exception:
            return False

    if len(parts) >= 5 and _is_decimal_token(parts[-1]):
        # ... side | account... | amount | currency | rate
        rate_s = parts[-1]
        currency = parts[-2]
        amount_s = parts[-3]
        account = ":".join(parts[1:-3]) or parts[1]
        rate = formatters.decimal_from_str(rate_s)
        if rate <= 0:
            raise DomainError("exchange rate must be > 0")
    else:
        # ... side | account... | amount | currency
        currency = parts[-1]
        amount_s = parts[-2]
        account = ":".join(parts[1:-2]) or parts[1]
    amount = formatters.decimal_from_str(amount_s)
    if amount <= 0:
        raise DomainError("amount must be > 0")
    side_up = side.upper()
    if side_up not in {"DEBIT", "CREDIT"}:
        raise DomainError("side must be DEBIT or CREDIT")
    return EntryLineDTO(
        side=side_up,
        account_full_name=account,
        amount=amount,
        currency_code=currency.upper(),
        exchange_rate=rate,
    )


def _parse_meta(meta_items: list[str]) -> dict[str, Any]:
    """Parse repeated --meta k=v items into dict."""
    result: dict[str, Any] = {}
    for item in meta_items:
        if "=" not in item:
            raise DomainError(f"Invalid meta item (expected k=v): {item}")
        k, v = item.split("=", 1)
        result[k] = v
    return result


def _apply_policy_arg(policy_name: str | None) -> ExchangeRatePolicy | None:
    """Return ExchangeRatePolicy from CLI argument or None."""
    if not policy_name:
        return None
    name = policy_name.lower()
    if name not in {"last_write", "weighted_average"}:
        raise DomainError(f"Unknown policy: {policy_name}")
    return ExchangeRatePolicy(mode=name)


def _configure_logging_from_flags(args: argparse.Namespace) -> None:
    """Apply log-related CLI flags to environment then configure logging."""
    try:
        from infrastructure.config import settings as settings_mod  # type: ignore
        if hasattr(settings_mod, "_cached"):
            settings_mod._cached = None
        if args.log_level:
            os.environ["LOG_LEVEL"] = args.log_level
        if args.json_logs:
            os.environ["JSON_LOGS"] = "true"
        if args.db_url:
            os.environ["DATABASE_URL"] = args.db_url
    except Exception:  # pragma: no cover
        pass
    configure_logging()


def build_parser() -> argparse.ArgumentParser:
    """Build top-level CLI argument parser with all subcommands."""
    p = argparse.ArgumentParser(prog="py_accountant", description="Accounting CLI (double-entry)")
    p.add_argument("--db-url", dest="db_url", help="Database URL (if omitted: in-memory)")
    p.add_argument("--log-level", dest="log_level", default="INFO", help="Log level")
    p.add_argument("--json-logs", dest="json_logs", action="store_true", help="Enable JSON structured logs")
    p.add_argument("--policy", dest="policy", help="Exchange rate policy (last_write|weighted_average)")
    p.add_argument("--json", dest="json_out", action="store_true", help="Output JSON instead of human-readable text")

    sub = p.add_subparsers(dest="command", required=True)

    cur_add = sub.add_parser("currency:add", help="Add currency (code)")
    cur_add.add_argument("code")
    cur_add.add_argument("--json", dest="json_out", action="store_true")

    cur_list = sub.add_parser("currency:list", help="List currencies")
    cur_list.add_argument("--json", dest="json_out", action="store_true")

    cur_base = sub.add_parser("currency:set-base", help="Set base currency")
    cur_base.add_argument("code")
    cur_base.add_argument("--json", dest="json_out", action="store_true")

    fx_up = sub.add_parser("fx:update", help="Update single currency rate")
    fx_up.add_argument("code")
    fx_up.add_argument("rate")
    fx_up.add_argument("--json", dest="json_out", action="store_true")

    fx_batch = sub.add_parser(
        "fx:batch",
        help="Batch update rates from JSON file (list of {code, rate})",
    )
    fx_batch.add_argument("path")
    fx_batch.add_argument("--policy", dest="local_policy", help="Override policy for this batch (last_write|weighted_average)")
    fx_batch.add_argument("--json", dest="json_out", action="store_true")

    acc_add = sub.add_parser("account:add", help="Add account")
    acc_add.add_argument("full_name")
    acc_add.add_argument("currency_code")
    acc_add.add_argument("--json", dest="json_out", action="store_true")

    tx_post = sub.add_parser("tx:post", help="Post transaction (balanced lines)")
    tx_post.add_argument("--memo", dest="memo", default="")
    tx_post.add_argument(
        "--meta", dest="meta", action="append", default=[], help="Metadata k=v (repeatable)"
    )
    tx_post.add_argument(
        "--line",
        dest="lines",
        action="append",
        required=True,
        help="Line: side:account:amount:currency[:rate]",
    )
    tx_post.add_argument("--json", dest="json_out", action="store_true")

    bal_get = sub.add_parser("balance:get", help="Get account balance")
    bal_get.add_argument("account")
    bal_get.add_argument("--as-of", dest="as_of")
    bal_get.add_argument("--json", dest="json_out", action="store_true")

    bal_re = sub.add_parser("balance:recalc", help="Recompute account balance")
    bal_re.add_argument("account")
    bal_re.add_argument("--as-of", dest="as_of")
    bal_re.add_argument("--json", dest="json_out", action="store_true")

    t_bal = sub.add_parser(
        "trading:balance", help="Aggregate trading balance (optional base infer)"
    )
    t_bal.add_argument("--base", dest="base")
    t_bal.add_argument("--as-of", dest="as_of")
    t_bal.add_argument("--start", dest="start")
    t_bal.add_argument("--end", dest="end")
    t_bal.add_argument("--json", dest="json_out", action="store_true")

    t_det = sub.add_parser(
        "trading:detailed", help="Detailed trading balance (requires base)"
    )
    t_det.add_argument("--base", dest="base", required=True)
    t_det.add_argument("--as-of", dest="as_of")
    t_det.add_argument("--start", dest="start")
    t_det.add_argument("--end", dest="end")
    t_det.add_argument("--normalize", dest="normalize", action="store_true", help="Normalize converted_* fields to MONEY_SCALE before output")
    t_det.add_argument("--json", dest="json_out", action="store_true")

    # rates audit
    diag_rates_audit = sub.add_parser("diagnostics:rates-audit", help="Show FX rate audit events (newest first)")
    diag_rates_audit.add_argument("--limit", dest="limit", type=int, help="Limit events per currency")
    diag_rates_audit.add_argument("--code", dest="code", action="append", help="Filter by currency code (repeatable)")
    diag_rates_audit.add_argument("--json", dest="json_out", action="store_true")

    led_list = sub.add_parser("ledger:list", help="List ledger entries for account")
    led_list.add_argument("account")
    led_list.add_argument("--start", dest="start")
    led_list.add_argument("--end", dest="end")
    led_list.add_argument("--offset", dest="offset", type=int, default=0)
    led_list.add_argument("--limit", dest="limit", type=int)
    led_list.add_argument("--order", dest="order", default="ASC")
    led_list.add_argument("--meta", dest="meta", action="append", default=[], help="Metadata filter k=v")
    led_list.add_argument("--json", dest="json_out", action="store_true")

    diag_rates = sub.add_parser("diagnostics:rates", help="Show currencies with rates/base flag and active policy")
    diag_rates.add_argument("--json", dest="json_out", action="store_true")

    # New diagnostics
    diag_parity = sub.add_parser("diagnostics:parity-report", help="Compare legacy Book vs new engine on preset or JSON scenarios")
    diag_parity.add_argument("--preset", dest="preset", default="default", help="Preset name (default)")
    diag_parity.add_argument("--scenarios-file", dest="scenarios_file", help="Path to scenarios JSON")
    diag_parity.add_argument("--expected-file", dest="expected_file", help="Path to expected results JSON (internal consistency when legacy absent)")
    diag_parity.add_argument("--tolerance", dest="tolerance", default="0.01", help="Money tolerance for parity deltas")
    diag_parity.add_argument("--json", dest="json_out", action="store_true")

    diag_rates_hist = sub.add_parser("diagnostics:rates-history", help="Show in-memory FX rates history for currencies")
    diag_rates_hist.add_argument("--limit", dest="limit", type=int, help="Override history length for output only")
    diag_rates_hist.add_argument("--json", dest="json_out", action="store_true")

    # Maintenance: FX TTL/archive
    fx_ttl = sub.add_parser("maintenance:fx-ttl", help="Apply TTL/archive policy for exchange_rate_events")
    fx_ttl.add_argument("--mode", dest="mode", choices=["none", "delete", "archive"], help="Mode: none|delete|archive")
    fx_ttl.add_argument("--retention-days", dest="retention_days", type=int, help="Retention days (events older than now-retention)" )
    fx_ttl.add_argument("--batch-size", dest="batch_size", type=int, help="Batch size for processing")
    fx_ttl.add_argument("--dry-run", dest="dry_run", action="store_true", help="Do not modify DB; just report counts")
    fx_ttl.add_argument("--json", dest="json_out", action="store_true")

    return p


def _print(obj: Any, json_out: bool) -> None:
    """Pretty-print DTOs or lists preserving legacy human-readable format."""
    if json_out:
        out = formatters.dataclass_to_dict(obj)
        print(json.dumps(out, indent=2))
        return
    if isinstance(obj, list):
        for item in obj:
            _print(item, False)
        return
    if hasattr(obj, "__dataclass_fields__"):
        cls_name = obj.__class__.__name__
        if cls_name == "CurrencyDTO":
            rate = getattr(obj, "exchange_rate", None)
            base = getattr(obj, "is_base", False)
            print(f"Currency {obj.code} base={base} rate={rate}")
            return
        if cls_name == "AccountDTO":
            print(f"Account {obj.full_name} currency={obj.currency_code}")
            return
        if cls_name == "TransactionDTO":
            print(f"Transaction {obj.id} lines={len(obj.lines)} memo={obj.memo}")
            return
        if cls_name == "TradingBalanceDTO":
            print(
                f"TradingBalance as_of={obj.as_of.isoformat()} base={obj.base_currency} total={obj.base_total}"
            )
            for line in obj.lines:
                bal = formatters.human_decimal(line.balance)
                cbal = formatters.human_decimal(line.converted_balance)
                print(
                    f"  {line.currency_code} debit={formatters.human_decimal(line.total_debit)} credit={formatters.human_decimal(line.total_credit)} bal={bal} converted={cbal} rate_used={line.rate_used} fallback={line.rate_fallback}"
                )
            return
        if cls_name == "RichTransactionDTO":
            print(
                f"RichTransaction {obj.id} at={obj.occurred_at.isoformat()} memo={obj.memo} lines={len(obj.lines)}"
            )
            return
    print(obj)


def _get_uow(db_url: str | None):
    """Deprecated: retained for tests that monkeypatch `_get_uow` to trigger errors.

    Runtime no longer uses sync UoW; this exists only to keep test hooks working.
    Returns a string token with the URL for identification.
    """
    # This function is intentionally not used by CLI dispatch anymore.
    return {"db_url": db_url or os.environ.get("DATABASE_URL")}


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point: parse args, dispatch command, preserve output format."""
    parser = build_parser()
    args = parser.parse_args(argv)
    log = get_logger("cli")
    try:
        _configure_logging_from_flags(args)
        # Acquire (deprecated) UoW hook early for tests that monkeypatch it to raise.
        # Not used for runtime logic; errors bubble as unexpected.
        _ = _get_uow(args.db_url)
        policy = _apply_policy_arg(args.policy)
        cmd = args.command
        log.info("cli.command", command=cmd)

        def _validate_currency_code(code: str) -> str:
            if not code or len(code) < 2 or len(code) > 10:
                raise DomainError("Invalid currency code length (2..10)")
            up = code.upper()
            if not up.isascii() or not up.replace("_", "").isalnum():
                raise DomainError("Currency code must be ASCII alnum + '_' only")
            return up

        def _validate_account_full_name(name: str) -> str:
            if not name or name.startswith(":") or name.endswith(":") or "::" in name:
                raise DomainError("Account full name has empty segment")
            segments = name.split(":")
            for seg in segments:
                if seg.strip() != seg:
                    raise DomainError("Account segment has leading/trailing spaces")
                if " " in seg:
                    raise DomainError("Account segment must not contain spaces")
                if any(not (c.isalnum() or c == "_") for c in seg):
                    raise DomainError("Account name segments must be alnum/_ only")
            return name

        if cmd == "currency:add":
            code = _validate_currency_code(args.code)
            dto = create_currency_sync(code)
            _print(dto, args.json_out)
            return 0
        if cmd == "currency:list":
            lst = list_currencies_sync()
            _print(lst, args.json_out)
            return 0
        if cmd == "currency:set-base":
            code = _validate_currency_code(args.code)
            cur_found = any(c.code == code for c in list_currencies_sync())
            if not cur_found:
                raise DomainError(f"Currency not found: {code}")
            result = set_base_currency_sync(code)
            _print(result, args.json_out)
            return 0
        if cmd == "fx:update":
            code = _validate_currency_code(args.code)
            rate = formatters.decimal_from_str(args.rate)
            if rate <= 0:
                raise DomainError("Rate must be > 0")
            if not get_currency_sync(code):
                raise DomainError(f"Currency not found: {code}")
            updated = set_currency_rate_sync(code, policy.apply(None, rate) if policy else rate, policy_applied=policy.mode if policy else "none", source="cli:fx:update")
            _history_append(updated.code, updated.exchange_rate or rate)
            _print(updated, args.json_out)
            return 0
        if cmd == "fx:batch":
            local_policy = _apply_policy_arg(getattr(args, "local_policy", None)) or policy
            path = Path(args.path)
            if not path.exists():
                raise DomainError(f"File not found: {path}")
            raw = path.read_text(encoding="utf-8").strip()
            if not raw:
                _print({"updated": 0}, args.json_out)
                return 0
            data = json.loads(raw)
            if not isinstance(data, list):
                raise DomainError("Batch JSON must be a list")
            dedup: dict[str, Decimal] = {}
            for item in data:
                if not isinstance(item, dict) or "code" not in item or "rate" not in item:
                    raise DomainError("Each item must have code and rate")
                code = _validate_currency_code(str(item["code"]))
                rate_val = formatters.decimal_from_str(str(item["rate"]))
                if rate_val <= 0:
                    raise DomainError("Rate must be > 0 in batch")
                dedup[code] = rate_val
            for code in dedup:
                if not get_currency_sync(code):
                    raise DomainError(f"Currency not found: {code}")
            applied: list[tuple[str, Decimal]] = []
            for code, r in dedup.items():
                new_rate = local_policy.apply(None, r) if local_policy else r
                applied.append((code, new_rate))
            updated_count = bulk_upsert_rates_sync(applied, policy_applied=(local_policy or policy).mode if (local_policy or policy) else "none", source="cli:fx:batch")
            for code, r in applied:
                _history_append(code, r)
            _print({"updated": updated_count}, args.json_out)
            return 0
        if cmd == "account:add":
            full = _validate_account_full_name(args.full_name)
            cur_code = _validate_currency_code(args.currency_code)
            dto_acc = create_account_sync(full, cur_code)
            _print(dto_acc, args.json_out)
            return 0
        if cmd == "tx:post":
            lines_raw: list[str] = getattr(args, "lines", []) or []
            dto_lines: list[EntryLineDTO] = [_parse_line(r) for r in lines_raw]
            meta_items: list[str] = getattr(args, "meta", [])
            meta_dict = _parse_meta(meta_items) if meta_items else {}
            tx = post_transaction_sync(dto_lines, memo=args.memo, meta=meta_dict)
            _print(tx, args.json_out)
            return 0
        if cmd == "balance:get":
            acct = _validate_account_full_name(args.account)
            as_of = _parse_iso8601(getattr(args, "as_of", None))
            bal = get_account_balance_sync(acct, as_of=as_of)
            _print({"account": acct, "balance": str(bal)}, args.json_out)
            return 0
        if cmd == "balance:recalc":
            acct = _validate_account_full_name(args.account)
            as_of = _parse_iso8601(getattr(args, "as_of", None))
            bal = get_account_balance_sync(acct, as_of=as_of)
            _print({"account": acct, "balance": str(bal)}, args.json_out)
            return 0
        if cmd == "ledger:list":
            acct = _validate_account_full_name(args.account)
            start = _parse_iso8601(getattr(args, "start", None))
            end = _parse_iso8601(getattr(args, "end", None))
            meta_items: list[str] = getattr(args, "meta", [])
            meta_dict = _parse_meta(meta_items) if meta_items else None
            rows = get_ledger_sync(
                acct,
                start,
                end,
                meta_dict,
                offset=getattr(args, "offset", 0),
                limit=getattr(args, "limit", None),
                order=getattr(args, "order", "ASC"),
            )
            _print(rows, args.json_out)
            return 0
        if cmd == "trading:balance":
            as_of = _parse_iso8601(getattr(args, "as_of", None))
            start = _parse_iso8601(getattr(args, "start", None))
            end = _parse_iso8601(getattr(args, "end", None))
            if start and end and start > end:
                raise DomainError("start > end")
            tb = get_trading_balance_sync(as_of=as_of, base_currency=args.base, start=start, end=end)
            _print(tb, args.json_out)
            return 0
        if cmd == "trading:detailed":
            as_of = _parse_iso8601(getattr(args, "as_of", None))
            start = _parse_iso8601(getattr(args, "start", None))
            end = _parse_iso8601(getattr(args, "end", None))
            if start and end and start > end:
                raise DomainError("start > end")
            tb = get_trading_balance_detailed_sync(
                base_currency=args.base,
                as_of=as_of,
                start=start,
                end=end,
            )
            if getattr(args, "normalize", False):
                for line in tb.lines:
                    if line.converted_debit is not None:
                        line.converted_debit = money_quantize(line.converted_debit)
                    if line.converted_credit is not None:
                        line.converted_credit = money_quantize(line.converted_credit)
                    if line.converted_balance is not None:
                        line.converted_balance = money_quantize(line.converted_balance)
                if tb.base_total is not None:
                    tb.base_total = money_quantize(tb.base_total)
            _print(tb, args.json_out)
            return 0
        if cmd == "diagnostics:rates-audit":
            codes: list[str] | None = getattr(args, "code", None)
            limit = getattr(args, "limit", None)
            coll: list[dict[str, Any]] = []
            if codes:
                for c in codes:
                    evs = list_exchange_rate_events_sync(c.upper(), limit)
                    coll.append({
                        "code": c.upper(),
                        "events": [
                            {
                                "rate": str(e.rate),
                                "occurred_at": e.occurred_at.isoformat().replace("+00:00", "Z"),
                                "policy": e.policy_applied,
                                "source": e.source,
                            }
                            for e in evs
                        ],
                        "count": len(evs),
                    })
            else:
                all_events = list_exchange_rate_events_sync(limit=None)
                seen: list[str] = []
                for e in all_events:
                    if e.code not in seen:
                        seen.append(e.code)
                for c in sorted(seen):
                    evs = list_exchange_rate_events_sync(c, limit)
                    coll.append({
                        "code": c,
                        "events": [
                            {
                                "rate": str(e.rate),
                                "occurred_at": e.occurred_at.isoformat().replace("+00:00", "Z"),
                                "policy": e.policy_applied,
                                "source": e.source,
                            }
                            for e in evs
                        ],
                        "count": len(evs),
                    })
            out = {"currencies": coll, "limit": limit}
            if args.json_out:
                print(json.dumps(out, indent=2))
            else:
                for item in coll:
                    print(f"{item['code']} count={item['count']}")
            return 0
        if cmd == "diagnostics:rates":
            cur_list = list_currencies_sync()
            result = []
            active_policy = policy.mode if policy else None
            for cur in cur_list:
                result.append({"code": cur.code, "rate": str(cur.exchange_rate) if cur.exchange_rate is not None else None, "is_base": cur.is_base, "policy": active_policy})
            _print(result, args.json_out)
            return 0
        if cmd == "diagnostics:rates-history":
            cur_list = list_currencies_sync()
            codes = [c.code for c in cur_list]
            snap = _history_snapshot(codes, limit=getattr(args, "limit", None))
            if args.json_out:
                print(json.dumps(snap, indent=2))
            else:
                for item in snap:
                    print(f"{item['code']}: count={item['count']} rates={item['rates']}")
            return 0
        if cmd == "maintenance:fx-ttl":
            try:
                from infrastructure.config.settings import get_settings  # type: ignore
                s = get_settings()
            except Exception:
                s = None
            mode = getattr(args, "mode", None) or (s.fx_ttl_mode if s else "none")
            retention_days = getattr(args, "retention_days", None) or (s.fx_ttl_retention_days if s else 90)
            batch_size = getattr(args, "batch_size", None) or (s.fx_ttl_batch_size if s else 1000)
            dry_run = bool(getattr(args, "dry_run", False) or (s.fx_ttl_dry_run if s else False))
            result = fx_ttl_apply_sync(mode=mode, retention_days=int(retention_days), batch_size=int(batch_size), dry_run=dry_run)
            if args.json_out:
                print(json.dumps(result, indent=2))
            else:
                print(
                    "fx-ttl: mode={mode} scanned={scanned} affected={affected} archived={archived} deleted={deleted} batches={batches} cutoff={cut}".format(
                        mode=result["mode"],
                        scanned=result["scanned"],
                        affected=result["affected"],
                        archived=result["archived"],
                        deleted=result["deleted"],
                        batches=result["batches"],
                        cut=(datetime.now(UTC) - timedelta(days=int(result["retention_days"])) ).isoformat().replace("+00:00", "Z"),
                    )
                )
            return 0
        if cmd == "diagnostics:parity-report":
            try:
                from presentation.cli.diagnostics import run_parity_report  # type: ignore
            except Exception:
                skipped = {"scenarios": [], "summary": {"total": 0, "matched": 0, "diverged": 0}}
                if args.json_out:
                    print(json.dumps(skipped, indent=2))
                else:
                    print("parity-report: skipped (module missing)")
                return 0
            tolerance = formatters.decimal_from_str(getattr(args, "tolerance", "0.01"))
            report = run_parity_report(preset=getattr(args, "preset", "default"), scenarios_path=getattr(args, "scenarios_file", None), expected_path=getattr(args, "expected_file", None), tolerance=tolerance)
            if args.json_out:
                print(json.dumps(report, indent=2))
            else:
                summary = report.get("summary", {})
                print(f"parity-report: total={summary.get('total')} matched={summary.get('matched')} diverged={summary.get('diverged')}")
            return 0
        raise DomainError(f"Unknown command: {cmd}")
    except DomainError as de:
        print(f"Error: {de}", file=sys.stderr)
        log.warning("cli.domain_error", error=str(de))
        return 2
    except Exception as exc:
        print(f"Unexpected error: {exc}", file=sys.stderr)
        log.error("cli.unexpected_error", error=str(exc))
        return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
