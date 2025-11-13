"""Async ledger CLI commands (I24).

Provides Typer sub-app with minimal commands: post, list, balance. Controllers are
thin: parse/normalize inputs, delegate to async use cases using an ephemeral async
UnitOfWork per command (infra.run_ephemeral_async_uow), and print human or JSON.

Exit codes are handled in main.cli: success=0; ValidationError/DomainError/ValueError=2;
unexpected=1. JSON keys use snake_case; Decimal values serialized as strings.
"""
from __future__ import annotations

import csv
import json
import re
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from typer import Argument, Option, Typer

from application.dto.models import EntryLineDTO, RichTransactionDTO, TransactionDTO
from application.use_cases_async.ledger import (
    AsyncGetAccountBalance,
    AsyncGetLedger,
    AsyncPostTransaction,
)
from domain.errors import ValidationError
from domain.quantize import money_quantize
from py_accountant.sdk import errors as sdk_errors

from .infra import run_ephemeral_async_uow

ledger = Typer(help="Ledger operations")


# --- Local helpers (parsing/formatting) ---

def _parse_amount(val: str, *, kind: str = "Amount") -> Decimal:
    """Parse Decimal via str(x); enforce > 0.

    kind controls error prefix: "Amount" or "Rate"; raises ValidationError with
    friendly hint like "Amount must be > 0" / "Rate must be > 0" or "Invalid Amount".
    """
    try:
        amt = Decimal(str(val).strip())
    except Exception as exc:  # noqa: PERF203
        raise ValidationError(f"Invalid {kind}") from exc
    if amt <= 0:
        raise ValidationError(f"{kind} must be > 0")
    return amt


def _parse_line(spec: str) -> EntryLineDTO:
    """Parse a --line spec: SIDE:Account:Amount:Currency[:Rate].

    Supports account names with nested ':' by taking the first field as side,
    the last fields as amount/currency[/rate], and the middle joined by ':' as
    account_full_name. Normalizes side/currency to upper; trims strings.

    Errors:
      - Format -> ValidationError("Invalid line format. Expected 'SIDE:Account:Amount:Currency[:Rate]'")
      - Amount/rate non-positive -> ValidationError("Amount must be > 0" / "Rate must be > 0")
      - SIDE not in {DEBIT,CREDIT} -> ValidationError("Invalid side; expected DEBIT or CREDIT")
      - Currency pattern mismatch -> ValidationError("Invalid currency; expected A-Z, len 3..10")
    """
    parts = (spec or "").split(":")
    if len(parts) < 4:
        raise ValidationError("Invalid line format. Expected 'SIDE:Account:Amount:Currency[:Rate]'")
    side_raw = (parts[0] or "").strip().upper()

    # Try to detect optional rate by validating trailing tokens
    rate_raw: str | None = None
    currency_raw: str
    amount_raw: str
    account: str

    # Candidate path with rate (at least 5 tokens needed)
    has_rate_layout = len(parts) >= 5
    if has_rate_layout:
        cur_candidate = parts[-2]
        rate_candidate = parts[-1]
        # Validate currency pattern first
        cur_ok = bool(re.fullmatch(r"[A-Z]{3,10}", (cur_candidate or "").strip().upper()))
        rate_ok = False
        if cur_ok:
            try:
                # Positive decimal
                rate_ok = Decimal(str(rate_candidate).strip()) > 0
            except Exception:  # noqa: PERF203 - falling back to no-rate layout
                rate_ok = False
        if cur_ok and rate_ok:
            currency_raw = cur_candidate
            rate_raw = rate_candidate
            amount_raw = parts[-3]
            account = ":".join(parts[1:-3]).strip()
        else:
            # Fallback to no-rate layout
            currency_raw = parts[-1]
            amount_raw = parts[-2]
            account = ":".join(parts[1:-2]).strip()
    else:
        currency_raw = parts[-1]
        amount_raw = parts[-2]
        account = ":".join(parts[1:-2]).strip()

    if not account:
        raise ValidationError("Invalid line format. Expected 'SIDE:Account:Amount:Currency[:Rate]'")

    # Validate side
    if side_raw not in {"DEBIT", "CREDIT"}:
        raise ValidationError("Invalid side; expected DEBIT or CREDIT")

    # Amount
    amount = _parse_amount(amount_raw, kind="Amount")

    # Currency validation
    currency = (currency_raw or "").strip().upper()
    if not re.fullmatch(r"[A-Z]{3,10}", currency or ""):
        raise ValidationError("Invalid currency; expected A-Z, len 3..10")

    # Optional rate
    exch_rate: Decimal | None = None
    if rate_raw is not None:
        exch_rate = _parse_amount(rate_raw or "", kind="Rate")

    return EntryLineDTO(
        side=side_raw,
        account_full_name=account,
        amount=amount,
        currency_code=currency,
        exchange_rate=exch_rate,
    )


def _parse_meta(items: list[str]) -> dict[str, str]:
    """Parse --meta k=v pairs into a dict; last duplicate wins.

    Raises ValidationError when item doesn't contain '=' or has empty key/value.
    """
    meta: dict[str, str] = {}
    for raw in items or []:
        if "=" not in raw:
            raise ValidationError("Invalid meta item; expected k=v")
        k, v = raw.split("=", 1)
        k = k.strip()
        v = v.strip()
        if not k or not v:
            raise ValidationError("Invalid meta item; empty key or value")
        meta[k] = v
    return meta


def _parse_iso_dt(value: str | None) -> datetime | None:
    """Parse ISO8601 datetime; naive treated as UTC.

    Returns aware datetime or None when value is None. Raises ValidationError on format.
    """
    if value is None:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except Exception as exc:  # noqa: PERF203
        raise ValidationError("Invalid datetime") from exc
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _clock_now_utc() -> datetime:
    # Simple UTC clock; no shared state
    return datetime.now(UTC)


def _tx_to_dict(tx: TransactionDTO) -> dict[str, Any]:
    return {
        "id": tx.id,
        "occurred_at": tx.occurred_at.isoformat(),
        "memo": tx.memo,
        "meta": tx.meta or {},
        "lines": [
            {
                "side": str(line.side),
                "account_full_name": line.account_full_name,
                "amount": str(line.amount),
                "currency_code": line.currency_code,
            }
            for line in tx.lines
        ],
    }


def _rich_tx_to_dict(tx: RichTransactionDTO) -> dict[str, Any]:
    return {
        "id": tx.id,
        "occurred_at": tx.occurred_at.isoformat(),
        "memo": tx.memo,
        "meta": tx.meta or {},
        "lines": [
            {
                "side": str(line.side),
                "account_full_name": line.account_full_name,
                "amount": str(line.amount),
                "currency_code": line.currency_code,
            }
            for line in tx.lines
        ],
    }


def _load_lines_from_file(path: Path) -> list[str]:
    """Load transaction lines from a CSV or JSON file into parser string format.

    Supports:
      - CSV with headers: side,account,amount,currency[,rate]
      - JSON array of strings (already in parser format)
      - JSON array of objects with keys side, account, amount, currency[, rate]

    Returns list of strings in format "SIDE:Account:Amount:Currency[:Rate]".
    Errors:
      - File not found/empty/unsupported extension -> ValueError
      - Malformed CSV/JSON or missing required fields -> ValueError
    """
    if not path.exists():
        raise ValueError(f"File not found: {path}")
    if not path.is_file():
        raise ValueError(f"Not a file: {path}")

    suffix = path.suffix.lower()
    if suffix not in {".csv", ".json"}:
        raise ValueError("Unsupported file extension. Supported: .csv, .json")

    if suffix == ".csv":
        lines: list[str] = []
        try:
            with path.open("r", encoding="utf-8-sig", newline="") as fh:
                reader = csv.DictReader(fh)
                if reader.fieldnames is None:
                    raise ValueError("No lines in file")
                required = {"side", "account", "amount", "currency"}
                headers = {h.strip().lower() for h in reader.fieldnames if h is not None}
                missing = sorted(required - headers)
                if missing:
                    raise ValueError(f"CSV missing required fields: {', '.join(missing)}")
                for idx, row in enumerate(reader, start=2):  # data rows start at line 2
                    if row is None:
                        continue
                    # Build lower-cased, trimmed mapping
                    row_l = {
                        (k.strip().lower() if k is not None else ""): (str(v).strip() if v is not None else "")
                        for k, v in row.items()
                    }
                    side = row_l.get("side", "")
                    account = row_l.get("account", "")
                    amount = row_l.get("amount", "")
                    currency = row_l.get("currency", "")
                    rate = row_l.get("rate", "")

                    # Skip empty rows (all values empty)
                    if not any([side, account, amount, currency, rate]):
                        continue

                    # Validate presence of required
                    if not side:
                        raise ValueError(f"CSV row {idx}: missing 'side'")
                    if not account:
                        raise ValueError(f"CSV row {idx}: missing 'account'")
                    if not amount:
                        raise ValueError(f"CSV row {idx}: missing 'amount'")
                    if not currency:
                        raise ValueError(f"CSV row {idx}: missing 'currency'")

                    # Build parser string; keep amount/rate as strings; normalize side/currency to upper
                    side_up = side.strip().upper()
                    currency_up = currency.strip().upper()
                    spec = f"{side_up}:{account}:{amount}:{currency_up}"
                    if rate:
                        spec = f"{spec}:{rate}"
                    lines.append(spec)
        except ValueError:
            raise
        except Exception as exc:  # noqa: PERF203
            raise ValueError(f"Invalid CSV: {exc}") from exc
        if not lines:
            raise ValueError("No lines in file")
        return lines

    # JSON path
    try:
        with path.open("r", encoding="utf-8-sig") as fh:
            data = json.load(fh)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON: {exc.msg}") from exc
    except Exception as exc:  # noqa: PERF203
        raise ValueError(f"Invalid JSON: {exc}") from exc

    if not isinstance(data, list):
        raise ValueError("JSON must be an array of strings or objects")
    if not data:
        raise ValueError("No lines in file")

    out: list[str] = []
    for idx, it in enumerate(data, start=1):
        if isinstance(it, str):
            spec = it.strip()
            if spec:
                out.append(spec)
            continue
        if isinstance(it, dict):
            side = (str(it.get("side") or "")).strip()
            account = (str(it.get("account") or "")).strip()
            amount = (str(it.get("amount") or "")).strip()
            currency = (str(it.get("currency") or "")).strip()
            rate = (str(it.get("rate") or "")).strip()

            if not side or not account or not amount or not currency:
                raise ValueError(
                    f"JSON item {idx}: missing required keys (need side, account, amount, currency)"
                )
            spec = f"{side.upper()}:{account}:{amount}:{currency.upper()}"
            if rate:
                spec = f"{spec}:{rate}"
            out.append(spec)
            continue
        raise ValueError(f"JSON item {idx}: unsupported type {type(it).__name__}")

    if not out:
        raise ValueError("No lines in file")
    return out


# --- Commands ---

@ledger.command("post")
def ledger_post(
    line: list[str] = Option([], "--line", help="Transaction line: SIDE:ACCOUNT:AMOUNT:CURRENCY_CODE[:Rate]", show_default=False),  # noqa: B008
    memo: str | None = Option(None, "--memo", help="Optional memo text"),  # noqa: B008
    meta_items: list[str] = Option([], "--meta", help="Meta key=value pairs", show_default=False),  # noqa: B008
    occurred_at: str | None = Option(None, "--occurred-at", help="Override occurred_at (ISO8601, naive→UTC)", show_default=False),  # noqa: B008
    json_output: bool = Option(False, "--json", help="Output JSON"),  # noqa: B008
    lines_file: Path | None = Option(None, "--lines-file", help="Load lines from CSV or JSON file", show_default=False),  # noqa: B008
    idempotency_key: str | None = Option(None, "--idempotency-key", help="Idempotency key to make posting idempotent; overrides meta idempotency_key if both provided", show_default=False),  # noqa: B008
) -> None:
    """Post a balanced transaction to the ledger.

    Parameters:
        line: One or more --line entries formatted as SIDE:Account:Amount:Currency[:Rate].
        lines_file: Optional path to CSV/JSON file with lines; merged after --line values.
        memo: Optional memo text; stored as-is or null.
        meta_items: Optional k=v pairs; parsed into dict.
        occurred_at: Optional ISO timestamp to override clock.now() (treated as UTC when naive).
        idempotency_key: Optional key to ensure the same transaction id is returned on retry; empty/whitespace ignored.
        json_output: When True prints a JSON object; else a short human line.
    Errors/exit codes:
        ValidationError/DomainError/ValueError -> exit 2; unexpected -> 1 (handled by main.cli).
    """
    # Build raw line specs: first CLI lines in provided order, then file lines (if any)
    raw_specs: list[str] = []
    raw_specs.extend(line or [])
    if lines_file is not None:
        file_specs = _load_lines_from_file(lines_file)
        raw_specs.extend(file_specs)

    if not raw_specs:
        raise ValidationError("No lines provided")

    lines = [_parse_line(spec) for spec in raw_specs]
    meta = _parse_meta(meta_items)
    # Apply idempotency_key with priority over meta
    if idempotency_key is not None:
        key_norm = idempotency_key.strip()
        if key_norm:
            meta["idempotency_key"] = key_norm
    occurred_dt = _parse_iso_dt(occurred_at)

    async def _logic(uow):
        # Override clock.now() when occurred_at provided
        if occurred_dt is not None:
            clock = type("_Clock", (), {"now": staticmethod(lambda: occurred_dt)})()
        else:
            clock = type("_Clock", (), {"now": staticmethod(_clock_now_utc)})()
        use = AsyncPostTransaction(uow, clock)
        return await use(lines, memo, meta)

    try:
        tx = run_ephemeral_async_uow(_logic)
    except Exception as exc:  # map to friendly text then re-raise for exit code 2
        mapped = sdk_errors.map_exception(exc)
        text = str(mapped)
        # Preserve ValueError classification to keep main exit code logic
        if isinstance(exc, ValueError):
            raise ValueError(text) from exc
        raise ValidationError(text) from exc

    if json_output:
        print(json.dumps(_tx_to_dict(tx)))
        return
    print(f"Transaction {tx.id} lines={len(tx.lines)}")


@ledger.command("list")
def ledger_list(
    account_full_name: str = Argument(..., help="Target account full name (A:B[:C...])"),
    start: str | None = Option(None, "--start", help="Start datetime (ISO8601)"),  # noqa: B008
    end: str | None = Option(None, "--end", help="End datetime (ISO8601)"),  # noqa: B008
    meta_items: list[str] = Option([], "--meta", help="Meta key=value filters", show_default=False),  # noqa: B008
    offset: int = Option(0, "--offset", help="Pagination offset (>=0)"),  # noqa: B008
    limit: int | None = Option(None, "--limit", help="Optional limit (<=0 -> empty)"),  # noqa: B008
    order: str = Option("ASC", "--order", help="ASC or DESC"),  # noqa: B008
    json_output: bool = Option(False, "--json", help="Output JSON list"),  # noqa: B008
) -> None:
    """List ledger transactions for an account with window/pagination.

    Parameters:
        account_full_name: Required account (validated by use case).
        start/end: Optional ISO timestamps; naive interpreted as UTC.
        meta_items: Optional k=v filters; match exact key/value pairs.
        offset, limit, order: Pagination and ordering (by occurred_at).
        json_output: When True prints JSON list of transactions.
    Errors/exit codes:
        ValidationError/ValueError -> exit 2 (bad formats or order), unexpected -> 1.
    """
    norm_account = (account_full_name or "").strip()
    if not norm_account:
        raise ValidationError("Empty account_full_name")
    start_dt = _parse_iso_dt(start)
    end_dt = _parse_iso_dt(end)
    meta = _parse_meta(meta_items)
    ord_norm = (order or "").strip().upper() or "ASC"
    if ord_norm not in {"ASC", "DESC"}:
        raise ValueError("order must be ASC or DESC")

    async def _logic(uow):
        clock = type("_Clock", (), {"now": staticmethod(_clock_now_utc)})()
        use = AsyncGetLedger(uow, clock)
        return await use(
            norm_account,
            start_dt,
            end_dt,
            meta,
            offset=offset,
            limit=limit,
            order=ord_norm,
        )

    items = run_ephemeral_async_uow(_logic)
    if json_output:
        print(json.dumps([_rich_tx_to_dict(t) for t in items]))
        return
    for t in items:
        memo_show = t.memo if t.memo is not None else ""
        print(f"TX {t.occurred_at.isoformat()} id={t.id} lines={len(t.lines)} memo={memo_show}")


@ledger.command("balance")
def ledger_balance(
    account_full_name: str = Argument(..., help="Target account full name (A:B[:C...])"),
    as_of: str | None = Option(None, "--as-of", help="Balance 'as of' timestamp (ISO8601)"),  # noqa: B008
    json_output: bool = Option(False, "--json", help="Output JSON"),  # noqa: B008
) -> None:
    """Get account balance at a moment in time.

    Parameters:
        account_full_name: Required account identifier.
        as_of: Optional ISO timestamp; naive interpreted as UTC.
        json_output: When True prints JSON object {account_full_name,balance}.
    Errors/exit codes:
        ValidationError/ValueError -> exit 2; unexpected -> 1.
    """
    norm_account = (account_full_name or "").strip()
    if not norm_account:
        raise ValidationError("Empty account_full_name")
    as_of_dt = _parse_iso_dt(as_of)

    async def _logic(uow):
        clock = type("_Clock", (), {"now": staticmethod(_clock_now_utc)})()
        use = AsyncGetAccountBalance(uow, clock)
        return await use(norm_account, as_of_dt)

    bal = run_ephemeral_async_uow(_logic)
    if json_output:
        print(json.dumps({"account_full_name": norm_account, "balance": str(money_quantize(bal))}))
        return
    print(f"Balance {norm_account} = {money_quantize(bal)}")
