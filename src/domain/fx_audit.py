"""Domain-only utilities for FX audit TTL planning.

This module defines pure computation helpers to calculate a UTC cutoff timestamp,
identify events older than that cutoff, and build deterministic batch plans for
archival or deletion workflows. No I/O or infrastructure dependencies.
"""
from __future__ import annotations

import datetime as dt
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum

from .errors import ValidationError

__all__ = [
    "ExchangeRateEventRef",
    "ArchivalMode",
    "TTLConfig",
    "Batch",
    "FxAuditTTLService",
]


@dataclass(slots=True, frozen=True)
class ExchangeRateEventRef:
    """Lightweight reference to an exchange-rate event.

    Attributes:
        id: Positive identifier of the event (> 0).
        occurred_at: Event timestamp. Naive values are interpreted as UTC.
    """

    id: int
    occurred_at: dt.datetime


class ArchivalMode(str, Enum):
    """Archival operation mode for TTL processing."""

    NONE = "none"
    DELETE = "delete"
    ARCHIVE = "archive"


@dataclass(slots=True, frozen=True)
class TTLConfig:
    """Immutable TTL configuration for FX audit housekeeping.

    Note: Validation is performed by service methods. This container is kept
    simple and dependency-free.

    Attributes:
        mode: Archival operation mode.
        retention_days: Non-negative retention window in days. 0 means "now".
        batch_size: Positive batch size for processing.
        dry_run: If True, compute plans without side-effects (handled by app).
    """

    mode: ArchivalMode
    retention_days: int
    batch_size: int
    dry_run: bool = False


@dataclass(slots=True, frozen=True)
class Batch:
    """A contiguous processing window.

    Attributes:
        offset: Zero-based start index (>= 0).
        limit: Positive size of the batch (> 0).
    """

    offset: int
    limit: int


def _to_utc(dt_value: dt.datetime) -> dt.datetime:
    """Normalize a datetime to an aware UTC datetime.

    Naive values are interpreted as UTC. Aware values are converted to UTC.
    """

    if not isinstance(dt_value, dt.datetime):  # defensive to provide clearer errors
        raise ValidationError("Expected datetime value")
    if dt_value.tzinfo is None:
        return dt_value.replace(tzinfo=dt.UTC)
    return dt_value.astimezone(dt.UTC)


class FxAuditTTLService:
    """Pure domain service for TTL cutoff and batch planning.

    All methods are side-effect free and independent from repositories.
    """

    @staticmethod
    def make_cutoff(now: dt.datetime | None, retention_days: int) -> dt.datetime:
        """Compute an aware UTC cutoff given retention days.

        Args:
            now: Current time reference; naive treated as UTC. If None, uses
                 datetime.now(timezone.utc).
            retention_days: Non-negative days to retain; 0 means "now".
        Returns:
            A timezone-aware UTC datetime that is `now - retention_days` days.
        Raises:
            ValidationError: If retention_days < 0.
        """

        if retention_days < 0:
            raise ValidationError("retention_days must be >= 0")
        base_now = now if now is not None else dt.datetime.now(dt.UTC)
        now_utc = _to_utc(base_now)
        return now_utc - dt.timedelta(days=retention_days)

    @staticmethod
    def identify_old(
        events: Iterable[ExchangeRateEventRef],
        cutoff: dt.datetime,
    ) -> list[ExchangeRateEventRef]:
        """Filter events strictly older than the cutoff.

        Contract: stable filtering without reordering. Naive timestamps are
        interpreted as UTC; aware timestamps are converted to UTC.

        Args:
            events: Iterable of event refs to check.
            cutoff: Threshold timestamp; naive treated as UTC.
        Returns:
            List of events with occurred_at < cutoff, preserving input order.
        Raises:
            ValidationError: If an event has invalid id (<= 0) or occurred_at is
                             not a datetime; or cutoff is not a datetime.
        """

        cutoff_utc = _to_utc(cutoff)
        result: list[ExchangeRateEventRef] = []
        for e in events:
            # Validate id first to fail fast on obviously bad input
            if not isinstance(e.id, int) or e.id <= 0:
                raise ValidationError("event.id must be a positive int")
            if not isinstance(e.occurred_at, dt.datetime):
                raise ValidationError("event.occurred_at must be a datetime")
            occurred_utc = _to_utc(e.occurred_at)
            if occurred_utc < cutoff_utc:
                result.append(e)
        return result

    @staticmethod
    def batch_plan(total: int, batch_size: int) -> list[Batch]:
        """Build a deterministic plan of contiguous, non-overlapping batches.

        Args:
            total: Total number of items to cover (>= 0).
            batch_size: Positive batch size (> 0).
        Returns:
            List of Batch windows covering [0..total) exactly. Empty if total=0.
        Raises:
            ValidationError: If total < 0 or batch_size <= 0.
        """

        if not isinstance(total, int) or total < 0:
            raise ValidationError("total must be a non-negative int")
        if not isinstance(batch_size, int) or batch_size <= 0:
            raise ValidationError("batch_size must be a positive int")
        if total == 0:
            return []
        batches: list[Batch] = []
        bcount = (total + batch_size - 1) // batch_size
        for i in range(bcount):
            offset = i * batch_size
            remaining = total - offset
            limit = batch_size if remaining >= batch_size else remaining
            batches.append(Batch(offset=offset, limit=limit))
        return batches
