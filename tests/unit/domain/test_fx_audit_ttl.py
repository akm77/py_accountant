from __future__ import annotations

import datetime as dt

import pytest

from domain.errors import ValidationError
from domain.fx_audit import (
    Batch,
    ExchangeRateEventRef,
    FxAuditTTLService,
)


def test_identify_old_events():
    # Fixed now and cutoff
    now = dt.datetime(2025, 11, 11, 0, 0, 0, tzinfo=dt.UTC)
    cutoff = FxAuditTTLService.make_cutoff(now, retention_days=90)

    # Construct events around the cutoff
    older_aware = ExchangeRateEventRef(
        id=1, occurred_at=cutoff - dt.timedelta(seconds=1)
    )
    boundary_naive = ExchangeRateEventRef(
        id=2, occurred_at=(cutoff.replace(tzinfo=None))
    )
    newer_aware = ExchangeRateEventRef(
        id=3, occurred_at=cutoff + dt.timedelta(seconds=1)
    )

    # Mix order and tz-aware/naive
    events = [newer_aware, older_aware, boundary_naive]

    # Only strictly older should be returned, preserving input order
    result = FxAuditTTLService.identify_old(events, cutoff)
    assert [e.id for e in result] == [1]


@pytest.mark.parametrize(
    "total,batch_size,expected",
    [
        (0, 10, []),
        (5, 10, [Batch(0, 5)]),
        (10, 10, [Batch(0, 10)]),
        (25, 10, [Batch(0, 10), Batch(10, 10), Batch(20, 5)]),
        (
            101,
            20,
            [
                Batch(0, 20),
                Batch(20, 20),
                Batch(40, 20),
                Batch(60, 20),
                Batch(80, 20),
                Batch(100, 1),
            ],
        ),
    ],
)
def test_archival_plan_sizes(total, batch_size, expected):
    plan = FxAuditTTLService.batch_plan(total, batch_size)
    assert plan == expected
    # Check coverage and no overlaps
    if total == 0:
        assert plan == []
        return
    # Coverage [0..total)
    covered = 0
    for b in plan:
        assert b.offset == covered
        covered += b.limit
    assert covered == total


def test_make_cutoff_normalization_utc():
    base = dt.datetime(2025, 11, 11, 0, 0, 0)  # naive, assume UTC
    cutoff_naive = FxAuditTTLService.make_cutoff(base, 0)
    assert cutoff_naive.tzinfo is dt.UTC

    aware = base.replace(tzinfo=dt.UTC)
    cutoff_aware = FxAuditTTLService.make_cutoff(aware, 0)
    assert cutoff_aware == aware


def test_validation_errors():
    with pytest.raises(ValidationError):
        FxAuditTTLService.make_cutoff(dt.datetime.now(dt.UTC), -1)

    with pytest.raises(ValidationError):
        FxAuditTTLService.batch_plan(-1, 10)
    with pytest.raises(ValidationError):
        FxAuditTTLService.batch_plan(10, 0)

    # identify_old invalid event id
    bad_event = ExchangeRateEventRef(id=0, occurred_at=dt.datetime.now(dt.UTC))
    with pytest.raises(ValidationError):
        FxAuditTTLService.identify_old([bad_event], dt.datetime.now(dt.UTC))

    # identify_old invalid occurred_at
    class Dummy:
        def __init__(self):
            self.id = 1
            self.occurred_at = "not-a-datetime"

    with pytest.raises(ValidationError):
        FxAuditTTLService.identify_old([Dummy()], dt.datetime.now(dt.UTC))  # type: ignore[arg-type]
