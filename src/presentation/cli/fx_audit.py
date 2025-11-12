"""Async FX audit CLI commands (I26).

Provides Typer sub-app with minimal commands:
  - add-event: append manual FX exchange rate event
  - list: list events with optional currency/time window + pagination
  - ttl-plan: compute TTL archival plan (none/delete/archive) using async use case

Design / controller principles:
  - Async-only path; no sync bridge usage
  - Fresh ephemeral async UoW per command (infra.run_ephemeral_async_uow)
  - Parsing & normalization only in controller; validation/business rules delegated to use cases / repos
  - JSON output strictly snake_case; Decimal rendered as fixed 6-decimal strings; datetimes ISO8601 (UTC aware)
  - Deterministic ordering by occurred_at (ASC default) applied in controller (repository returns newest-first)
  - Error classification handled centrally in main.cli (ValidationError/ValueError -> exit 2)
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from collections.abc import Iterable

from typer import Argument, Option, Typer

from application.dto.models import ExchangeRateEventDTO, FxAuditTTLPlanDTO
from application.use_cases_async.fx_audit import (
    AsyncAddExchangeRateEvent,
    AsyncListExchangeRateEvents,
)
from application.use_cases_async.fx_audit_ttl import AsyncPlanFxAuditTTL
from domain.errors import ValidationError
from domain.quantize import rate_quantize

from .infra import run_ephemeral_async_uow

fx = Typer(help="FX audit tools")

# --- Helpers ---

def _parse_code(raw: str | None, *, required: bool = False) -> str | None:
    """Normalize a currency code (strip + upper).

    Returns None if not required and empty; raises ValidationError("Empty currency code")
    when required and blank/empty.
    """
    if raw is None:
        if required:
            raise ValidationError("Empty currency code")
        return None
    code = raw.strip().upper()
    if not code:
        if required:
            raise ValidationError("Empty currency code")
        return None
    return code


def _parse_rate(raw: str) -> Decimal:
    """Parse positive Decimal rate value.

    Raises ValidationError("Invalid rate") when parse fails or value <= 0.
    """
    try:
        rate = Decimal(str(raw))
    except (InvalidOperation, ValueError) as exc:  # noqa: PERF203
        raise ValidationError("Invalid rate") from exc
    if rate <= 0:
        raise ValidationError("Invalid rate")
    # Do not quantize for storage; keep precision from input, but for output we format to 6dp
    return rate


def _parse_iso_dt(value: str | None) -> datetime | None:
    """Parse ISO8601 datetime string; naive interpreted as UTC.

    Returns aware datetime or None. Raises ValidationError("Invalid datetime") on format.
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
    """Return current UTC datetime (aware)."""
    return datetime.now(UTC)


def _event_to_dict(e: ExchangeRateEventDTO) -> dict[str, Any]:
    """Serialize ExchangeRateEventDTO to JSON-safe dict with fixed formats."""
    # Rate: show fixed 6 decimals (business expectation) using quantize helper for consistency
    rate_fixed = rate_quantize(e.rate)
    return {
        "id": e.id,
        "code": e.code,
        "rate": f"{rate_fixed:.6f}",
        "occurred_at": e.occurred_at.astimezone(UTC).isoformat(),
        "policy_applied": e.policy_applied,
        "source": e.source,
    }


def _ttl_plan_to_dict(plan: FxAuditTTLPlanDTO) -> dict[str, Any]:
    """Serialize FxAuditTTLPlanDTO to dict (JSON snake_case)."""
    return {
        "cutoff": plan.cutoff.astimezone(UTC).isoformat(),
        "mode": plan.mode,
        "retention_days": plan.retention_days,
        "batch_size": plan.batch_size,
        "dry_run": plan.dry_run,
        "total_old": plan.total_old,
        "batches": [
            {"offset": b.offset, "limit": b.limit} for b in plan.batches
        ],
        "old_event_ids": plan.old_event_ids,
    }


def _apply_window(evts: Iterable[ExchangeRateEventDTO], start: datetime | None, end: datetime | None) -> list[ExchangeRateEventDTO]:
    """Filter events to inclusive [start, end] UTC window if provided."""
    out: list[ExchangeRateEventDTO] = []
    for e in evts:
        ts = e.occurred_at.astimezone(UTC)
        if start and ts < start:
            continue
        if end and ts > end:
            continue
        out.append(e)
    return out


def _order_events(evts: list[ExchangeRateEventDTO], order: str) -> list[ExchangeRateEventDTO]:
    """Order events by occurred_at (ASC/DESC) stable; secondary id for determinism."""
    asc = order == "ASC"
    return sorted(
        evts,
        key=lambda e: (e.occurred_at, e.id if e.id is not None else -1),
        reverse=not asc,
    )


# --- Commands ---

@fx.command("add-event")
def fx_add_event(
    code: str = Argument(..., help="Currency code"),
    rate: str = Argument(..., help="FX rate > 0"),
    occurred_at: str | None = Option(None, "--occurred-at", help="Event datetime ISO8601 (default now UTC)"),
    source: str | None = Option(None, "--source", help="Optional source tag"),
    json_output: bool = Option(False, "--json", help="Output JSON"),
) -> None:
    """Add (append) an exchange-rate audit event.

    Parameters: code (upper), rate (>0 Decimal), optional occurred_at ISO (naive->UTC), source tag.
    Outputs: JSON object or single human line. policy_applied fixed as 'manual'.
    Errors: ValidationError/ValueError -> exit 2 (handled by main.cli).
    """
    norm_code = _parse_code(code, required=True)  # type: ignore[arg-type]
    dec_rate = _parse_rate(rate)
    dt = _parse_iso_dt(occurred_at) or _clock_now_utc()
    src = (source.strip() if source is not None else "cli") or None

    async def _logic(uow):  # noqa: ANN001
        use = AsyncAddExchangeRateEvent(uow)
        return await use(norm_code, dec_rate, dt, "manual", src)

    evt = run_ephemeral_async_uow(_logic)
    if json_output:
        print(json.dumps(_event_to_dict(evt)))
        return
    src_show = evt.source if evt.source else "-"
    print(
        f"FX event {evt.id} ={_event_to_dict(evt)['rate']} at={evt.occurred_at.astimezone(UTC).isoformat()} "
        f"policy={evt.policy_applied} source={src_show}"
    )


@fx.command("list")
def fx_list(
    code: str | None = Option(None, "--code", help="Filter by currency code"),
    start: str | None = Option(None, "--start", help="Start datetime (ISO8601) inclusive"),
    end: str | None = Option(None, "--end", help="End datetime (ISO8601) inclusive"),
    offset: int = Option(0, "--offset", help="Pagination offset (>=0)"),
    limit: int | None = Option(None, "--limit", help="Limit (None unlimited, 0 => empty)"),
    order: str = Option("ASC", "--order", help="ASC or DESC"),
    json_output: bool = Option(False, "--json", help="Output JSON list"),
) -> None:
    """List FX audit events with optional filters and pagination.

    Filtering: code (upper), time window [start,end]. Ordering by occurred_at (ASC default).
    Pagination applied after ordering. limit=0 returns empty list. JSON outputs list of dicts.
    Errors: ValidationError/ValueError -> exit 2.
    """
    norm_code = _parse_code(code) if code else None
    start_dt = _parse_iso_dt(start)
    end_dt = _parse_iso_dt(end)
    if start_dt and end_dt and start_dt > end_dt:
        raise ValidationError("Invalid datetime window")
    if offset < 0:
        raise ValueError("offset must be >= 0")
    if order is None:
        order = "ASC"
    order_norm = order.strip().upper()
    if order_norm not in {"ASC", "DESC"}:
        raise ValueError("order must be ASC or DESC")
    if limit is not None and limit < 0:
        raise ValueError("limit must be >= 0")
    if limit == 0:
        # Short-circuit empty
        if json_output:
            print("[]")
        return

    async def _logic(uow):  # noqa: ANN001
        use = AsyncListExchangeRateEvents(uow)
        # Retrieve all (unbounded) for code filter then apply window/pagination
        return await use(norm_code, None)

    events = run_ephemeral_async_uow(_logic)
    filtered = _apply_window(events, start_dt, end_dt)
    ordered = _order_events(filtered, order_norm)
    # Apply offset/limit
    sliced = ordered[offset:]
    if limit is not None:
        sliced = sliced[:limit]
    if json_output:
        print(json.dumps([_event_to_dict(e) for e in sliced]))
        return
    for e in sliced:
        src_show = e.source if e.source else "-"
        print(
            f"FX {e.id} rate={_event_to_dict(e)['rate']} at={e.occurred_at.astimezone(UTC).isoformat()} "
            f"policy={e.policy_applied} source={src_show}"
        )


@fx.command("ttl-plan")
def fx_ttl_plan(
    mode: str = Option("none", "--mode", help="TTL mode: none|delete|archive"),
    retention_days: int = Option(90, "--retention-days", help="Retention window in days (>=0)"),
    batch_size: int = Option(1000, "--batch-size", help="Batch size (>0)"),
    limit: int | None = Option(None, "--limit", help="Cap number of candidate IDs (>=0)"),
    dry_run: bool = Option(True, "--dry-run/--no-dry-run", help="Dry run flag"),
    json_output: bool = Option(False, "--json", help="Output JSON"),
) -> None:
    """Compute FX audit TTL archival plan.

    Parameters: mode (none/delete/archive), retention_days>=0, batch_size>0, optional limit>=0.
    Produces plan JSON or human lines (header + batches). No side effects (planning only).
    Errors: ValidationError/ValueError -> exit 2.
    """
    # Validate primitive params early (mirroring TTL use case but with distinct messages per spec)
    m_norm = (mode or "none").strip().lower()
    if m_norm not in {"none", "delete", "archive"}:
        raise ValidationError("Invalid mode")
    if retention_days < 0:
        raise ValidationError("Invalid retention_days")
    if batch_size <= 0:
        raise ValidationError("Invalid batch_size")
    if limit is not None and limit < 0:
        raise ValidationError("Invalid limit")

    async def _logic(uow):  # noqa: ANN001
        clock = type("_Clock", (), {"now": staticmethod(_clock_now_utc)})()
        use = AsyncPlanFxAuditTTL(uow, clock)  # type: ignore[arg-type]
        return await use(retention_days=retention_days, batch_size=batch_size, mode=m_norm, limit=limit, dry_run=dry_run)

    plan = run_ephemeral_async_uow(_logic)
    if json_output:
        print(json.dumps(_ttl_plan_to_dict(plan)))
        return
    # Human output
    header = (
        f"TTL cutoff={plan.cutoff.astimezone(UTC).isoformat()} mode={plan.mode} retention_days={plan.retention_days} "
        f"batch_size={plan.batch_size} dry_run={plan.dry_run} total_old={plan.total_old} candidates={len(plan.old_event_ids)}"
    )
    print(header)
    for b in plan.batches:
        print(f"BATCH offset={b.offset} limit={b.limit}")
