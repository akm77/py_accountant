from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from infrastructure.persistence.sqlalchemy.uow import AsyncSqlAlchemyUnitOfWork

pytestmark = pytest.mark.asyncio


async def test_fx_ttl_archive_and_delete(async_uow: AsyncSqlAlchemyUnitOfWork):
    """End-to-end TTL archival and deletion behavior for FX events using async UoW."""
    uow = async_uow
    now = datetime.now(UTC)
    # Seed 5 old events and 2 fresh (non-archived expected)
    for i in range(5):
        await uow.exchange_rate_events.add_event(
            code="USD", rate=Decimal("1.0"), occurred_at=now - timedelta(days=30 + i), policy_applied="RAW", source="test"
        )
    for i in range(2):
        await uow.exchange_rate_events.add_event(
            code="USD", rate=Decimal("1.0"), occurred_at=now - timedelta(days=i), policy_applied="RAW", source="test"
        )
    cutoff = now - timedelta(days=10)
    archived, deleted = await uow.exchange_rate_events.move_events_to_archive(cutoff, limit=3, archived_at=now)
    assert archived == 3 and deleted == 3
    # Remaining old events should be 2
    old = await uow.exchange_rate_events.list_old_events(cutoff, limit=10)
    assert len(old) == 2
    # List newest first with limit
    newest = await uow.exchange_rate_events.list_events(code="USD", limit=2)
    assert len(newest) == 2 and newest[0].occurred_at >= newest[1].occurred_at
