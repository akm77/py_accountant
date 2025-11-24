from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from py_accountant.infrastructure.persistence.inmemory.repositories import (
    InMemoryExchangeRateEventsRepository,
)


def _mk_event(repo: InMemoryExchangeRateEventsRepository, code: str, rate: str, ts: datetime) -> None:
    repo.add_event(code, Decimal(rate), ts, policy_applied="none", source="test")


def test_delete_mode_removes_old_events():
    repo = InMemoryExchangeRateEventsRepository()
    now = datetime.now(UTC)
    old = now - timedelta(days=10)
    recent = now - timedelta(days=1)
    _mk_event(repo, "EUR", "1.1", old)
    _mk_event(repo, "EUR", "1.2", recent)
    rows = repo.list_old_events(now - timedelta(days=5), limit=100)
    assert len(rows) == 1
    deleted = repo.delete_events_by_ids([int(e.id) for e in rows if e.id is not None])
    assert deleted == 1
    remaining = repo.list_events()
    assert len(remaining) == 1
    assert remaining[0].rate == Decimal("1.2")


def test_archive_mode_moves_and_removes():
    repo = InMemoryExchangeRateEventsRepository()
    now = datetime.now(UTC)
    old = now - timedelta(days=10)
    _mk_event(repo, "EUR", "1.1", old)
    arch, dele = repo.move_events_to_archive(now - timedelta(days=5), limit=100, archived_at=now)
    assert arch == 1
    assert dele == 1
    assert repo.list_events() == []
    assert len(repo._archive_rows()) == 1
    assert repo._archive_rows()[0]["archived_at"] == now


def test_dry_run_changes_nothing():
    repo = InMemoryExchangeRateEventsRepository()
    now = datetime.now(UTC)
    old = now - timedelta(days=10)
    _mk_event(repo, "EUR", "1.1", old)
    # simulate dry-run: list only
    rows = repo.list_old_events(now - timedelta(days=5), limit=100)
    assert len(rows) == 1
    # no delete/archive
    assert len(repo.list_events()) == 1


def test_batching_respects_limit():
    repo = InMemoryExchangeRateEventsRepository()
    now = datetime.now(UTC)
    old = now - timedelta(days=10)
    for i in range(5):
        _mk_event(repo, "EUR", str(Decimal("1.0") + Decimal(i) / Decimal(10)), old)
    rows = repo.list_old_events(now - timedelta(days=5), limit=2)
    assert len(rows) == 2

