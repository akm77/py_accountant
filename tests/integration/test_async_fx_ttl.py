from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from py_accountant.application.use_cases_async import (
    AsyncAddExchangeRateEvent,
    AsyncExecuteFxAuditTTL,
    AsyncPlanFxAuditTTL,
)


@pytest.mark.asyncio
async def test_fx_ttl_plan_and_delete_flow(async_uow, mock_clock):
    """End-to-end TTL delete flow using async use cases and domain TTL planning."""
    now = mock_clock.now()
    adder = AsyncAddExchangeRateEvent(async_uow)
    # Seed 5 old events and 2 fresh (non-deleted expected)
    for i in range(5):
        await adder("USD", Decimal("1.0"), now - timedelta(days=30 + i), "RAW", "seed")
    for i in range(2):
        await adder("USD", Decimal("1.0"), now - timedelta(days=i), "RAW", "seed")
    planner = AsyncPlanFxAuditTTL(async_uow, mock_clock)
    plan = await planner(retention_days=10, batch_size=3, mode="delete")
    assert plan.total_old == 5
    executor = AsyncExecuteFxAuditTTL(async_uow, mock_clock)
    result = await executor(plan)
    assert result.deleted_count == 5 and result.archived_count == 0
    remaining_old = await async_uow.exchange_rate_events.list_old_events(plan.cutoff, 10)
    assert remaining_old == []
    # Newest events remain
    newest = await async_uow.exchange_rate_events.list_events(code="USD", limit=2)
    assert len(newest) == 2 and newest[0].occurred_at >= newest[1].occurred_at


@pytest.mark.asyncio
async def test_fx_ttl_plan_and_archive_flow(async_uow, mock_clock):
    """End-to-end TTL archive flow (archive+delete) using async use cases."""
    now = mock_clock.now()
    adder = AsyncAddExchangeRateEvent(async_uow)
    for i in range(4):
        await adder("EUR", Decimal("1.0"), now - timedelta(days=35 + i), "RAW", "seed")
    planner = AsyncPlanFxAuditTTL(async_uow, mock_clock)
    plan = await planner(retention_days=10, batch_size=2, mode="archive")
    assert plan.total_old == 4
    result = await AsyncExecuteFxAuditTTL(async_uow, mock_clock)(plan)
    assert result.archived_count == 4 and result.deleted_count == 4
    remaining_old = await async_uow.exchange_rate_events.list_old_events(plan.cutoff, 10)
    assert remaining_old == []


@pytest.mark.asyncio
async def test_fx_ttl_plan_large_events_batch_sizes(async_uow, mock_clock):
    """Sanity check: large number of events yields correct batch plan coverage."""
    now = mock_clock.now()
    adder = AsyncAddExchangeRateEvent(async_uow)
    for i in range(17):
        await adder("GBP", Decimal("1.0"), now - timedelta(days=50 + i), "RAW", "seed")
    plan = await AsyncPlanFxAuditTTL(async_uow, mock_clock)(retention_days=10, batch_size=5, mode="delete")
    assert plan.total_old == 17
    coverage = sum(b.limit for b in plan.batches)
    assert coverage == 17
    limits = [b.limit for b in plan.batches]
    assert limits == [5, 5, 5, 2]


# Provide deterministic clock fixture for integration tests (shared signature with unit tests)
@pytest.fixture
def mock_clock():
    class _Clock:
        def now(self):
            return datetime(2025, 11, 12, 12, 0, 0, tzinfo=UTC)
    return _Clock()
