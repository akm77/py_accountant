"""Async ledger CLI commands (I24).

Provides Typer sub-app with minimal commands: post, list, balance. Controllers are
thin: parse/normalize inputs, delegate to async use cases using an ephemeral async
UnitOfWork per command (infra.run_ephemeral_async_uow), and print human or JSON.

Exit codes are handled in main.cli: success=0; ValidationError/DomainError/ValueError=2;
unexpected=1. JSON keys use snake_case; Decimal values serialized as strings.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
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

from .infra import run_ephemeral_async_uow

ledger = Typer(help="Ledger operations")


# --- Local helpers (parsing/formatting) ---

def _parse_amount(val: str) -> Decimal:
    """Parse amount as Decimal via str(x); enforce > 0.

    Raises ValidationError("Invalid amount") on parse error or non-positive value.
    """
    try:
        amt = Decimal(str(val))
    except Exception as exc:  # noqa: PERF203
        raise ValidationError("Invalid amount") from exc
    if amt <= 0:
        raise ValidationError("Invalid amount")
    return amt


def _parse_line(spec: str) -> EntryLineDTO:
    """Parse a --line spec: SIDE:ACCOUNT_FULL_NAME:AMOUNT:CURRENCY_CODE.

    Supports account names with nested ':' by taking the first field as side,
    the last two as amount and currency, and the middle joined by ':' as the
    account_full_name. Normalizes side and currency to upper; trims strings.
    """
    parts = (spec or "").split(":")
    if len(parts) < 4:
        raise ValidationError("Invalid line format")
    side_raw = parts[0].strip().upper()
    currency = parts[-1].strip().upper()
    amount_raw = parts[-2]
    account = ":".join(parts[1:-2]).strip()
    if not account:
        raise ValidationError("Invalid line format")
    amount = _parse_amount(amount_raw)
    return EntryLineDTO(side=side_raw, account_full_name=account, amount=amount, currency_code=currency)


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
                "side": line.side if isinstance(line.side, str) else str(line.side.value),
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
                "side": line.side if isinstance(line.side, str) else str(line.side.value),
                "account_full_name": line.account_full_name,
                "amount": str(line.amount),
                "currency_code": line.currency_code,
            }
            for line in tx.lines
        ],
    }


# --- Commands ---

@ledger.command("post")
def ledger_post(
    line: list[str] = Option([], "--line", help="Transaction line: SIDE:ACCOUNT:AMOUNT:CURRENCY_CODE", show_default=False),
    memo: str | None = Option(None, "--memo", help="Optional memo text"),
    meta_items: list[str] = Option([], "--meta", help="Meta key=value pairs", show_default=False),
    json_output: bool = Option(False, "--json", help="Output JSON"),
) -> None:
    """Post a balanced transaction to the ledger.

    Parameters:
        line: One or more --line entries formatted as SIDE:ACCOUNT:AMOUNT:CURRENCY.
        memo: Optional memo text; stored as-is or null.
        meta_items: Optional k=v pairs; parsed into dict.
        json_output: When True prints a JSON object; else a short human line.
    Errors/exit codes:
        ValidationError/DomainError/ValueError -> exit 2; unexpected -> 1 (handled by main.cli).
    """
    if not line:
        raise ValidationError("No lines provided")
    lines = [_parse_line(l) for l in line]
    meta = _parse_meta(meta_items)

    async def _logic(uow):
        clock = type("_Clock", (), {"now": staticmethod(_clock_now_utc)})()
        use = AsyncPostTransaction(uow, clock)
        return await use(lines, memo, meta)

    tx = run_ephemeral_async_uow(_logic)
    if json_output:
        print(json.dumps(_tx_to_dict(tx)))
        return
    print(f"Transaction {tx.id} lines={len(tx.lines)}")


@ledger.command("list")
def ledger_list(
    account_full_name: str = Argument(..., help="Target account full name (A:B[:C...])"),
    start: str | None = Option(None, "--start", help="Start datetime (ISO8601)"),
    end: str | None = Option(None, "--end", help="End datetime (ISO8601)"),
    meta_items: list[str] = Option([], "--meta", help="Meta key=value filters", show_default=False),
    offset: int = Option(0, "--offset", help="Pagination offset (>=0)"),
    limit: int | None = Option(None, "--limit", help="Optional limit (<=0 -> empty)"),
    order: str = Option("ASC", "--order", help="ASC or DESC"),
    json_output: bool = Option(False, "--json", help="Output JSON list"),
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
    as_of: str | None = Option(None, "--as-of", help="Balance 'as of' timestamp (ISO8601)"),
    json_output: bool = Option(False, "--json", help="Output JSON"),
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

