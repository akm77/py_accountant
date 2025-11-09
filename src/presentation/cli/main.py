from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from application.dto.models import EntryLineDTO
from application.use_cases.ledger import (
    CreateAccount,
    CreateCurrency,
    GetBalance,
    GetTradingBalance,
    GetTradingBalanceDetailed,
    ListLedger,
    PostTransaction,
)
from application.utils.quantize import money_quantize
from domain.services.account_balance_service import (
    InMemoryAccountBalanceService,
    SqlAccountBalanceService,
)
from domain.services.exchange_rate_policy import ExchangeRatePolicy
from domain.value_objects import DomainError
from infrastructure.logging.config import configure_logging, get_logger
from infrastructure.persistence.inmemory.clock import SystemClock
from infrastructure.persistence.inmemory.uow import InMemoryUnitOfWork as MemUoW
from infrastructure.persistence.sqlalchemy.uow import SqlAlchemyUnitOfWork
from presentation.cli import formatters

# Global state (simple) to persist UoW across multiple main() invocations within same process
_GLOBAL: dict[str, Any] = {}


def _get_uow(db_url: str | None) -> Any:
    key = db_url or "__mem__"
    if not db_url:
        test_id = os.environ.get("PYTEST_CURRENT_TEST")
        if test_id:
            key = f"{key}:{test_id}"
    if key in _GLOBAL:
        return _GLOBAL[key]
    uow = SqlAlchemyUnitOfWork(db_url) if db_url else MemUoW()
    _GLOBAL[key] = uow
    return uow


def _parse_iso8601(value: str | None) -> datetime | None:
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
    # Format: side:account:amount:currency[:rate]
    # Account may contain ':' segments; parse from the end.
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
    result: dict[str, Any] = {}
    for item in meta_items:
        if "=" not in item:
            raise DomainError(f"Invalid meta item (expected k=v): {item}")
        k, v = item.split("=", 1)
        result[k] = v
    return result


def _apply_policy_arg(policy_name: str | None) -> ExchangeRatePolicy | None:
    if not policy_name:
        return None
    name = policy_name.lower()
    if name not in {"last_write", "weighted_average"}:
        raise DomainError(f"Unknown policy: {policy_name}")
    return ExchangeRatePolicy(mode=name)


def _configure_logging_from_flags(args: argparse.Namespace) -> None:
    try:
        from infrastructure.config import settings as settings_mod  # type: ignore
        if hasattr(settings_mod, "_cached"):
            settings_mod._cached = None
        import os
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
    t_bal.add_argument("--json", dest="json_out", action="store_true")

    t_det = sub.add_parser(
        "trading:detailed", help="Detailed trading balance (requires base)"
    )
    t_det.add_argument("--base", dest="base", required=True)
    t_det.add_argument("--as-of", dest="as_of")
    t_det.add_argument("--normalize", dest="normalize", action="store_true", help="Normalize converted_* fields to MONEY_SCALE before output")
    t_det.add_argument("--json", dest="json_out", action="store_true")

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

    return p


def _print(obj: Any, json_out: bool) -> None:
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


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    log = get_logger("cli")  # ensure available in exception handlers
    try:
        _configure_logging_from_flags(args)
        clock = SystemClock()
        uow = _get_uow(args.db_url)
        policy = _apply_policy_arg(args.policy)
        # Safe balances repository detection
        balances_repo = None
        try:
            balances_repo = getattr(uow, "balances", None)
        except Exception:
            balances_repo = None
        if balances_repo is not None:
            balance_service = SqlAccountBalanceService(transactions=uow.transactions, balances=balances_repo)  # type: ignore[arg-type]
        else:
            balance_service = InMemoryAccountBalanceService()
        cmd = args.command
        log.info("cli.command", command=cmd)
        # Helper validation functions
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
            uc = CreateCurrency(uow)
            dto = uc(code)
            uow.commit()
            _print(dto, args.json_out)
            return 0
        if cmd == "currency:list":
            lst = uow.currencies.list_all()
            _print(lst, args.json_out)
            return 0
        if cmd == "currency:set-base":
            code = _validate_currency_code(args.code)
            cur = uow.currencies.get_by_code(code)
            if not cur:
                raise DomainError(f"Currency not found: {code}")
            uow.currencies.set_base(cur.code)
            uow.commit()
            result = uow.currencies.get_base()
            _print(result, args.json_out)
            return 0
        if cmd == "fx:update":
            code = _validate_currency_code(args.code)
            rate = formatters.decimal_from_str(args.rate)
            if rate <= 0:
                raise DomainError("Rate must be > 0")
            cur = uow.currencies.get_by_code(code)
            if not cur:
                raise DomainError(f"Currency not found: {code}")
            prev = cur.exchange_rate
            cur.exchange_rate = policy.apply(prev, rate) if policy else rate
            uow.currencies.upsert(cur)
            uow.commit()
            _print(cur, args.json_out)
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
            # Last wins dedup: iterate, store in dict then apply
            dedup: dict[str, Decimal] = {}
            for item in data:
                if not isinstance(item, dict) or "code" not in item or "rate" not in item:
                    raise DomainError("Each item must have code and rate")
                code = _validate_currency_code(str(item["code"]))
                rate_val = formatters.decimal_from_str(str(item["rate"]))
                if rate_val <= 0:
                    raise DomainError("Rate must be > 0 in batch")
                dedup[code] = rate_val
            updates: list[tuple[str, Decimal]] = []
            for code, rate_val in dedup.items():
                cur = uow.currencies.get_by_code(code)
                if not cur:
                    raise DomainError(f"Currency not found: {code}")
                new_rate = local_policy.apply(cur.exchange_rate, rate_val) if local_policy else rate_val
                updates.append((code, new_rate))
            if updates:
                uow.currencies.bulk_upsert_rates(updates)
                uow.commit()
            _print({"updated": len(updates)}, args.json_out)
            return 0
        if cmd == "account:add":
            full = _validate_account_full_name(args.full_name)
            existing = uow.accounts.get_by_full_name(full)
            if existing:
                _print(existing, args.json_out)
                return 0
            code = _validate_currency_code(args.currency_code)
            uc = CreateAccount(uow)
            dto = uc(full, code)
            uow.commit()
            _print(dto, args.json_out)
            return 0
        if cmd == "tx:post":
            lines = [_parse_line(r) for r in args.lines]
            # Early balance check in base terms using provided exchange_rate when available.
            # This is a best-effort guard; domain TransactionVO will enforce strictly.
            try:
                total_base_debit = sum(
                    (line.amount / (line.exchange_rate if line.exchange_rate else Decimal("1")))
                    for line in lines
                    if line.side.upper() == "DEBIT"
                )
                total_base_credit = sum(
                    (line.amount / (line.exchange_rate if line.exchange_rate else Decimal("1")))
                    for line in lines
                    if line.side.upper() == "CREDIT"
                )
                if total_base_debit.quantize(Decimal("1.0000000000")) != total_base_credit.quantize(Decimal("1.0000000000")):
                    raise DomainError("Unbalanced transaction: total_debit != total_credit")
            except Exception:  # pragma: no cover - safety
                pass
            meta = _parse_meta(args.meta)
            uc = PostTransaction(uow=uow, clock=clock, balance_service=balance_service, rate_policy=policy)
            tx = uc(lines=lines, memo=args.memo, meta=meta)
            uow.commit()
            _print(tx, args.json_out)
            return 0
        if cmd == "balance:get":
            as_of = _parse_iso8601(args.as_of)
            uc = GetBalance(uow=uow, clock=clock, balance_service=balance_service)
            bal = uc(args.account, as_of=as_of)
            _print({"account": args.account, "balance": str(bal)}, args.json_out)
            return 0
        if cmd == "balance:recalc":
            as_of = _parse_iso8601(args.as_of)
            uc = GetBalance(uow=uow, clock=clock, balance_service=balance_service)
            bal = uc(args.account, as_of=as_of, recompute=True)
            _print({"account": args.account, "balance": str(bal)}, args.json_out)
            return 0
        if cmd == "trading:balance":
            as_of = _parse_iso8601(args.as_of)
            uc = GetTradingBalance(uow=uow, clock=clock)
            tb = uc(base_currency=args.base, as_of=as_of)
            _print(tb, args.json_out)
            return 0
        if cmd == "trading:detailed":
            as_of = _parse_iso8601(args.as_of)
            uc = GetTradingBalanceDetailed(uow=uow, clock=clock)
            tb = uc(base_currency=args.base, as_of=as_of)
            if args.normalize:
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
        if cmd == "ledger:list":
            start = _parse_iso8601(args.start)
            end = _parse_iso8601(args.end)
            meta_filter = _parse_meta(args.meta)
            uc = ListLedger(uow=uow, clock=clock)
            result = uc(args.account, start=start, end=end, meta=meta_filter or None, offset=args.offset, limit=args.limit, order=args.order)
            _print(result, args.json_out)
            return 0
        if cmd == "diagnostics:rates":
            cur_list = uow.currencies.list_all()
            result = []
            active_policy = policy.mode if policy else None
            for cur in cur_list:
                result.append({"code": cur.code, "rate": str(cur.exchange_rate) if cur.exchange_rate is not None else None, "is_base": cur.is_base, "policy": active_policy})
            _print(result, args.json_out)
            return 0
        raise DomainError(f"Unknown command: {cmd}")
    except DomainError as de:  # domain validation error
        print(f"Error: {de}", file=sys.stderr)
        log.warning("cli.domain_error", error=str(de))
        return 2
    except Exception as exc:  # unexpected
        print(f"Unexpected error: {exc}", file=sys.stderr)
        log.error("cli.unexpected_error", error=str(exc))
        return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
