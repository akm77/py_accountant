from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC

from application.dto.models import BatchDTO, FxAuditTTLPlanDTO, FxAuditTTLResultDTO
from application.interfaces.ports import AsyncUnitOfWork, Clock
from domain.errors import ValidationError
from domain.fx_audit import FxAuditTTLService

VALID_MODES = {"NONE": "none", "DELETE": "delete", "ARCHIVE": "archive"}
_MAX_SCAN = 100_000  # safety cap for full scan when limit is None


def _normalize_mode(value: str) -> str:
    up = value.strip().upper()
    if up not in VALID_MODES:
        raise ValidationError("unknown TTL mode")
    return VALID_MODES[up]


@dataclass(slots=True)
class AsyncPlanFxAuditTTL:
    """Compute FX audit TTL plan (cutoff + candidate IDs + batch windows).

    Parameters:
        uow: AsyncUnitOfWork providing exchange_rate_events repo.
        clock: Clock for deterministic cutoff (UTC expected).

    Call Args:
        retention_days: Non-negative retention window (0 => now).
        batch_size: Positive batch size (>0).
        mode: 'none' | 'delete' | 'archive' (case-insensitive).
        limit: Optional cap on number of old event IDs captured in plan.
        dry_run: If True, execution will report 0 side-effects.

    Returns:
        FxAuditTTLPlanDTO describing cutoff, batching and old_event_ids.

    Raises:
        ValidationError: invalid arguments (negative days, non-positive batch size, bad mode, negative limit).
        ValueError: missing repository (unlikely misconfiguration).
    """

    uow: AsyncUnitOfWork
    clock: Clock

    async def __call__(
        self,
        retention_days: int,
        batch_size: int,
        mode: str = "none",
        limit: int | None = None,
        dry_run: bool = False,
    ) -> FxAuditTTLPlanDTO:
        if retention_days < 0:
            raise ValidationError("retention_days must be >= 0")
        if batch_size <= 0:
            raise ValidationError("batch_size must be > 0")
        if limit is not None and limit < 0:
            raise ValidationError("limit must be >= 0")
        norm_mode = _normalize_mode(mode)
        now = self.clock.now()
        cutoff = FxAuditTTLService.make_cutoff(now, retention_days)
        # Full scan of old events (up to cap) to determine total_old and candidate IDs
        full_rows = await self.uow.exchange_rate_events.list_old_events(cutoff, _MAX_SCAN)
        total_old = len(full_rows)
        candidate_rows = full_rows[:limit] if limit is not None else full_rows
        old_ids = [int(r.id) for r in candidate_rows if r.id is not None]
        batches = FxAuditTTLService.batch_plan(total_old, batch_size) if total_old > 0 else []
        return FxAuditTTLPlanDTO(
            cutoff=cutoff,
            mode=norm_mode,
            retention_days=retention_days,
            batch_size=batch_size,
            dry_run=dry_run,
            total_old=total_old,
            batches=[BatchDTO(b.offset, b.limit) for b in batches],
            old_event_ids=old_ids,
        )


@dataclass(slots=True)
class AsyncExecuteFxAuditTTL:
    """Execute previously computed TTL plan: archive/delete or no-op/dry-run.

    Parameters:
        uow: AsyncUnitOfWork with exchange_rate_events repo.
        clock: Clock for archive timestamp.

    Call Args:
        plan: FxAuditTTLPlanDTO produced by AsyncPlanFxAuditTTL.

    Behavior:
        - dry_run => counts remain zero, batches_executed=0.
        - mode 'none' => no side effects.
        - mode 'delete' => delete IDs slice per batch.
        - mode 'archive' => archive then delete (two-phase) per batch.

    Returns:
        FxAuditTTLResultDTO summarizing execution effects.

    Raises:
        ValidationError: plan inconsistent (e.g. empty IDs with delete/archive, batch coverage mismatch).
        ValueError: missing repository.
    """

    uow: AsyncUnitOfWork
    clock: Clock

    async def __call__(self, plan: FxAuditTTLPlanDTO) -> FxAuditTTLResultDTO:
        # Basic plan consistency checks
        if plan.mode not in {"none", "delete", "archive"}:
            raise ValidationError("plan.mode invalid")
        if plan.batch_size <= 0:
            raise ValidationError("plan.batch_size must be > 0")
        if plan.total_old < 0:
            raise ValidationError("plan.total_old must be >= 0")
        covered = sum(b.limit for b in plan.batches)
        if plan.total_old == 0 and covered != 0:
            raise ValidationError("batches must be empty when total_old==0")
        if plan.total_old > 0 and covered != plan.total_old:
            raise ValidationError("batches coverage mismatch total_old")
        if plan.mode != "none" and not plan.old_event_ids:
            raise ValidationError("no candidate IDs to process for mode")

        if plan.dry_run or plan.mode == "none":
            return FxAuditTTLResultDTO(
                executed_mode=plan.mode,
                archived_count=0,
                deleted_count=0,
                dry_run=plan.dry_run,
                batches_executed=0,
                cutoff=plan.cutoff,
            )

        archived_total = 0
        deleted_total = 0
        batches_executed = 0
        for b in plan.batches:
            if b.limit <= 0:
                continue
            slice_ids = plan.old_event_ids[b.offset : b.offset + b.limit]
            if not slice_ids:
                raise ValidationError("batch slice empty for provided IDs")
            if plan.mode == "archive":
                rows = await self.uow.exchange_rate_events.list_old_events(plan.cutoff, len(plan.old_event_ids))
                rows_map = {int(r.id): r for r in rows if r.id is not None}
                selected_rows = [rows_map[i] for i in slice_ids if i in rows_map]
                archived_at = self.clock.now().astimezone(UTC)
                archived_count = await self.uow.exchange_rate_events.archive_events(selected_rows, archived_at)
                archived_total += archived_count
                deleted_count = await self.uow.exchange_rate_events.delete_events_by_ids(slice_ids)
                deleted_total += deleted_count
            elif plan.mode == "delete":
                deleted_count = await self.uow.exchange_rate_events.delete_events_by_ids(slice_ids)
                deleted_total += deleted_count
            batches_executed += 1

        return FxAuditTTLResultDTO(
            executed_mode=plan.mode,
            archived_count=archived_total,
            deleted_count=deleted_total,
            dry_run=plan.dry_run,
            batches_executed=batches_executed,
            cutoff=plan.cutoff,
        )
