from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from typer import Option, Typer

from application.use_cases_async.trading_balance import (
    AsyncGetTradingBalanceDetailed,
    AsyncGetTradingBalanceRaw,
)
from domain.errors import ValidationError
from domain.quantize import money_quantize

from .infra import run_ephemeral_async_uow

trading = Typer(help="Trading balance reports")


# --- Local helpers (parsing/clock) ---

def _parse_iso_dt(value: str | None) -> datetime | None:
    """Parse ISO8601 datetime; naive values are treated as UTC.

    Returns aware datetime or None for missing value. Raises ValidationError("Invalid datetime") on parse error.
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


def _parse_meta(items: list[str]) -> dict[str, str]:
    """Parse --meta k=v pairs into a dict; last duplicate wins.

    Raises ValidationError for missing '=' or empty key/value.
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


def _clock_now_utc() -> datetime:
    """Return now() in UTC timezone for use by async use cases."""
    return datetime.now(UTC)


def _simple_line_to_dict(line: Any) -> dict[str, Any]:
    # DTO fields: currency_code, debit, credit, net (Decimal -> str)
    return {
        "currency_code": line.currency_code,
        "debit": str(Decimal(str(line.debit))),
        "credit": str(Decimal(str(line.credit))),
        "net": str(Decimal(str(line.net))),
    }


def _detailed_line_to_dict(line: Any) -> dict[str, Any]:
    # DTO fields: currency_code, base_currency_code, debit, credit, net, used_rate, debit_base, credit_base, net_base
    return {
        "currency_code": line.currency_code,
        "base_currency_code": line.base_currency_code,
        "debit": str(Decimal(str(line.debit))),
        "credit": str(Decimal(str(line.credit))),
        "net": str(Decimal(str(line.net))),
        "used_rate": str(Decimal(str(line.used_rate))),
        "debit_base": str(Decimal(str(line.debit_base))),
        "credit_base": str(Decimal(str(line.credit_base))),
        "net_base": str(Decimal(str(line.net_base))),
    }


# --- Commands ---

@trading.command("raw")
def trading_raw(
    start: str | None = Option(None, "--start", help="Start datetime (ISO8601)"),
    end: str | None = Option(None, "--end", help="End datetime (ISO8601)"),
    meta_items: list[str] = Option([], "--meta", help="Meta key=value filters", show_default=False),
    json_output: bool = Option(False, "--json", help="Output JSON list"),
) -> None:
    """Report aggregated raw trading balance per currency (no conversion).

    Parameters:
        start/end: Optional ISO timestamps; naive interpreted as UTC.
        meta_items: Optional k=v filters (exact match); last duplicate wins.
        json_output: When True prints JSON list; else prints one human line per currency.
    Errors/exit codes: ValidationError/ValueError -> exit 2; unexpected -> 1 (handled by main.cli).
    """
    start_dt = _parse_iso_dt(start)
    end_dt = _parse_iso_dt(end)
    meta = _parse_meta(meta_items)

    async def _logic(uow):
        clock = type("_Clock", (), {"now": staticmethod(_clock_now_utc)})()
        use = AsyncGetTradingBalanceRaw(uow, clock)
        return await use(start=start_dt, end=end_dt, meta=meta)

    lines = run_ephemeral_async_uow(_logic)
    if json_output:
        print(json.dumps([_simple_line_to_dict(l) for l in lines]))
        return
    for l in lines:
        print(
            " ".join(
                [
                    f"RAW {l.currency_code}",
                    f"debit={money_quantize(l.debit)}",
                    f"credit={money_quantize(l.credit)}",
                    f"net={money_quantize(l.net)}",
                ]
            )
        )


@trading.command("detailed")
def trading_detailed(
    start: str | None = Option(None, "--start", help="Start datetime (ISO8601)"),
    end: str | None = Option(None, "--end", help="End datetime (ISO8601)"),
    meta_items: list[str] = Option([], "--meta", help="Meta key=value filters", show_default=False),
    base: str | None = Option(None, "--base", help="Explicit base currency code"),
    json_output: bool = Option(False, "--json", help="Output JSON list"),
) -> None:
    """Report aggregated trading balance with conversion to base currency.

    Parameters:
        start/end: Optional ISO timestamps; naive interpreted as UTC.
        meta_items: Optional k=v filters (exact match).
        base: Optional explicit base currency code (upper/trim); empty -> ValidationError.
        json_output: When True prints JSON list; else prints one human line per currency.
    Errors/exit codes: ValidationError/ValueError -> exit 2; unexpected -> 1 (handled by main.cli).
    """
    start_dt = _parse_iso_dt(start)
    end_dt = _parse_iso_dt(end)
    meta = _parse_meta(meta_items)
    base_norm: str | None
    if base is None:
        base_norm = None
    else:
        b = base.strip().upper()
        if not b:
            raise ValidationError("Empty base currency code")
        base_norm = b

    async def _logic(uow):
        clock = type("_Clock", (), {"now": staticmethod(_clock_now_utc)})()
        use = AsyncGetTradingBalanceDetailed(uow, clock)
        return await use(start=start_dt, end=end_dt, meta=meta, base_currency=base_norm)

    lines = run_ephemeral_async_uow(_logic)
    if json_output:
        print(json.dumps([_detailed_line_to_dict(l) for l in lines]))
        return
    for l in lines:
        print(
            " ".join(
                [
                    f"DET {l.currency_code}",
                    f"base={l.base_currency_code}",
                    f"rate={l.used_rate}",
                    f"debit={money_quantize(l.debit)}",
                    f"credit={money_quantize(l.credit)}",
                    f"net={money_quantize(l.net)}",
                    f"debit_base={money_quantize(l.debit_base)}",
                    f"credit_base={money_quantize(l.credit_base)}",
                    f"net_base={money_quantize(l.net_base)}",
                ]
            )
        )

