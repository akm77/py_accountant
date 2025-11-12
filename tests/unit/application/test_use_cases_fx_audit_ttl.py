from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from application.dto.models import FxAuditTTLPlanDTO
from application.use_cases_async import (
    AsyncAddExchangeRateEvent,
    AsyncExecuteFxAuditTTL,
    AsyncPlanFxAuditTTL,
)
from domain.errors import ValidationError


@pytest.mark.asyncio
async def test_plan_ttl_empty_events_returns_empty_batches(async_uow, mock_clock):
    planner = AsyncPlanFxAuditTTL(async_uow, mock_clock)
    plan = await planner(retention_days=10, batch_size=5, mode="none")
    assert plan.total_old == 0
    assert plan.batches == []
    assert plan.old_event_ids == []


@pytest.mark.asyncio
async def test_plan_ttl_negative_retention_raises_validation_error(async_uow, mock_clock):
    planner = AsyncPlanFxAuditTTL(async_uow, mock_clock)
    with pytest.raises(ValidationError):
        await planner(retention_days=-1, batch_size=10)


@pytest.mark.asyncio
async def test_plan_ttl_zero_retention_cutoff_now(async_uow, mock_clock):
    planner = AsyncPlanFxAuditTTL(async_uow, mock_clock)
    plan = await planner(retention_days=0, batch_size=10)
    assert plan.cutoff == mock_clock.now()


@pytest.mark.asyncio
async def test_plan_ttl_batch_plan_matches_total(async_uow, mock_clock):
    now = mock_clock.now()
    # Seed 7 old events
    adder = AsyncAddExchangeRateEvent(async_uow)
    for i in range(7):
        await adder("USD", Decimal("1.0"), now - timedelta(days=30 + i), "RAW", "seed")
    planner = AsyncPlanFxAuditTTL(async_uow, mock_clock)
    plan = await planner(retention_days=10, batch_size=3, mode="delete")
    assert plan.total_old == 7
    covered = sum(b.limit for b in plan.batches)
    assert covered == plan.total_old
    # Expect 3 batches: 3,3,1
    limits = [b.limit for b in plan.batches]
    assert limits == [3, 3, 1]


@pytest.mark.asyncio
async def test_plan_ttl_limit_restricts_old_event_ids(async_uow, mock_clock):
    now = mock_clock.now()
    adder = AsyncAddExchangeRateEvent(async_uow)
    for i in range(5):
        await adder("EUR", Decimal("1.0"), now - timedelta(days=20 + i), "RAW", "seed")
    planner = AsyncPlanFxAuditTTL(async_uow, mock_clock)
    plan = await planner(retention_days=10, batch_size=10, limit=2, mode="delete")
    assert plan.total_old == 5
    assert len(plan.old_event_ids) == 2


@pytest.mark.asyncio
async def test_execute_ttl_dry_run_no_side_effects(async_uow, mock_clock):
    now = mock_clock.now()
    adder = AsyncAddExchangeRateEvent(async_uow)
    for i in range(3):
        await adder("USD", Decimal("1.0"), now - timedelta(days=15 + i), "RAW", "seed")
    plan = await AsyncPlanFxAuditTTL(async_uow, mock_clock)(retention_days=10, batch_size=2, mode="delete", dry_run=True)
    executor = AsyncExecuteFxAuditTTL(async_uow, mock_clock)
    res = await executor(plan)
    assert res.deleted_count == 0 and res.archived_count == 0 and res.batches_executed == 0
    # ensure events still present
    remaining = await async_uow.exchange_rate_events.list_old_events(plan.cutoff, 10)
    assert len(remaining) == 3


@pytest.mark.asyncio
async def test_execute_ttl_mode_none_no_side_effects(async_uow, mock_clock):
    now = mock_clock.now()
    adder = AsyncAddExchangeRateEvent(async_uow)
    for i in range(2):
        await adder("USD", Decimal("1.0"), now - timedelta(days=12 + i), "RAW", "seed")
    plan = await AsyncPlanFxAuditTTL(async_uow, mock_clock)(retention_days=10, batch_size=10, mode="none")
    res = await AsyncExecuteFxAuditTTL(async_uow, mock_clock)(plan)
    assert res.deleted_count == 0 and res.archived_count == 0 and res.batches_executed == 0
    assert res.executed_mode == "none"


@pytest.mark.asyncio
async def test_execute_ttl_delete_mode_removes_events(async_uow, mock_clock):
    now = mock_clock.now()
    adder = AsyncAddExchangeRateEvent(async_uow)
    for i in range(4):
        await adder("USD", Decimal("1.0"), now - timedelta(days=25 + i), "RAW", "seed")
    plan = await AsyncPlanFxAuditTTL(async_uow, mock_clock)(retention_days=10, batch_size=2, mode="delete")
    res = await AsyncExecuteFxAuditTTL(async_uow, mock_clock)(plan)
    assert res.deleted_count == 4 and res.archived_count == 0 and res.batches_executed == 2
    remaining = await async_uow.exchange_rate_events.list_old_events(plan.cutoff, 10)
    assert remaining == []


@pytest.mark.asyncio
async def test_execute_ttl_archive_mode_archives_events(async_uow, mock_clock):
    now = mock_clock.now()
    adder = AsyncAddExchangeRateEvent(async_uow)
    for i in range(3):
        await adder("EUR", Decimal("1.0"), now - timedelta(days=40 + i), "RAW", "seed")
    plan = await AsyncPlanFxAuditTTL(async_uow, mock_clock)(retention_days=10, batch_size=2, mode="archive")
    res = await AsyncExecuteFxAuditTTL(async_uow, mock_clock)(plan)
    assert res.archived_count == 3 and res.deleted_count == 3
    # After archive+delete, old list should be empty
    remaining = await async_uow.exchange_rate_events.list_old_events(plan.cutoff, 10)
    assert remaining == []


@pytest.mark.asyncio
async def test_execute_ttl_invalid_mode_raises_validation_error(async_uow, mock_clock):
    # Craft invalid plan manually (simulate tampering)
    bad = FxAuditTTLPlanDTO(
        cutoff=mock_clock.now(),
        mode="invalid",
        retention_days=1,
        batch_size=1,
        dry_run=False,
        total_old=0,
        batches=[],
        old_event_ids=[],
    )
    executor = AsyncExecuteFxAuditTTL(async_uow, mock_clock)
    with pytest.raises(ValidationError):
        await executor(bad)


@pytest.mark.asyncio
async def test_execute_ttl_no_ids_with_delete_mode_raises(async_uow, mock_clock):
    plan = FxAuditTTLPlanDTO(
        cutoff=mock_clock.now(),
        mode="delete",
        retention_days=1,
        batch_size=1,
        dry_run=False,
        total_old=1,
        batches=[type("B", (), {"offset": 0, "limit": 1})()],  # minimal batch stub
        old_event_ids=[],
    )
    executor = AsyncExecuteFxAuditTTL(async_uow, mock_clock)
    with pytest.raises(ValidationError):
        await executor(plan)


# Simple clock fixture for deterministic now
def _fixed_now():
    return datetime(2025, 11, 12, 12, 0, 0, tzinfo=UTC)


@pytest.fixture
def mock_clock():
    class _C:
        def now(self):
            return _fixed_now()
    return _C()

