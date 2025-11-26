"""Unit tests for MigrationRunner."""

from __future__ import annotations

from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine

from py_accountant.infrastructure.migrations.errors import VersionMismatchError
from py_accountant.infrastructure.migrations.runner import MigrationRunner


@pytest_asyncio.fixture
async def test_db_engine(tmp_path: Path):
    """File-based SQLite engine for tests."""
    db_path = tmp_path / "test_migrations.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", echo=False)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def runner(test_db_engine):
    """MigrationRunner instance for tests."""
    return MigrationRunner(test_db_engine)


@pytest.mark.asyncio
async def test_migration_runner_initialization(test_db_engine):
    """MigrationRunner can be initialized."""
    runner = MigrationRunner(test_db_engine)

    assert runner.engine is test_db_engine
    assert runner.echo is False
    assert runner._config is not None


@pytest.mark.asyncio
async def test_migration_runner_initialization_with_echo(test_db_engine):
    """MigrationRunner can be initialized with echo enabled."""
    runner = MigrationRunner(test_db_engine, echo=True)

    assert runner.engine is test_db_engine
    assert runner.echo is True


@pytest.mark.asyncio
async def test_upgrade_to_head(runner):
    """upgrade_to_head() applies all migrations."""
    # Should not raise
    await runner.upgrade_to_head()

    # Check current version
    current = await runner.get_current_version()
    assert current == "0008_add_account_aggregates"  # Last migration


@pytest.mark.asyncio
async def test_upgrade_to_specific_version(runner):
    """upgrade_to_version() applies migrations up to specific version."""
    await runner.upgrade_to_version("0005_exchange_rate_events_archive")

    current = await runner.get_current_version()
    assert current == "0005_exchange_rate_events_archive"


@pytest.mark.asyncio
async def test_downgrade(runner):
    """downgrade() rolls back migrations."""
    # Upgrade to head first
    await runner.upgrade_to_head()
    assert await runner.get_current_version() == "0008_add_account_aggregates"

    # Downgrade 2 steps
    await runner.downgrade(steps=2)

    current = await runner.get_current_version()
    assert current == "0006_add_journal_idempotency_key"


@pytest.mark.asyncio
async def test_downgrade_to_target(runner):
    """downgrade() can target specific version."""
    # Upgrade to head first
    await runner.upgrade_to_head()
    assert await runner.get_current_version() == "0008_add_account_aggregates"

    # Downgrade to specific version
    await runner.downgrade(target="0003_add_performance_indexes")

    current = await runner.get_current_version()
    assert current == "0003_add_performance_indexes"


@pytest.mark.asyncio
async def test_downgrade_to_base(runner):
    """downgrade() can roll back to base."""
    # Upgrade to a version first
    await runner.upgrade_to_version("0005_exchange_rate_events_archive")
    assert await runner.get_current_version() == "0005_exchange_rate_events_archive"

    # Downgrade to base
    await runner.downgrade(target="base")

    current = await runner.get_current_version()
    assert current is None


@pytest.mark.asyncio
async def test_get_current_version_uninitialized(runner):
    """get_current_version() returns None for uninitialized database."""
    current = await runner.get_current_version()
    assert current is None


@pytest.mark.asyncio
async def test_get_current_version_after_upgrade(runner):
    """get_current_version() returns correct version after upgrade."""
    await runner.upgrade_to_version("0003_add_performance_indexes")

    current = await runner.get_current_version()
    assert current == "0003_add_performance_indexes"


@pytest.mark.asyncio
async def test_get_pending_migrations_uninitialized(runner):
    """get_pending_migrations() returns all migrations for uninitialized DB."""
    pending = await runner.get_pending_migrations()

    # Should have all 8 migrations
    assert len(pending) == 8
    # Check that migrations are in the list
    pending_str = str(pending)
    assert "0001_initial" in pending_str
    assert "0008_add_account_aggregates" in pending_str


@pytest.mark.asyncio
async def test_get_pending_migrations_partial(runner):
    """get_pending_migrations() returns remaining migrations after partial upgrade."""
    # Upgrade to 0003
    await runner.upgrade_to_version("0003_add_performance_indexes")

    pending = await runner.get_pending_migrations()

    # Should have 5 pending (0004-0008)
    assert len(pending) == 5


@pytest.mark.asyncio
async def test_get_pending_migrations_at_head(runner):
    """get_pending_migrations() returns empty list when at head."""
    # Upgrade to head
    await runner.upgrade_to_head()

    pending = await runner.get_pending_migrations()

    # Should have no pending migrations
    assert len(pending) == 0


@pytest.mark.asyncio
async def test_validate_schema_version_success(runner):
    """validate_schema_version() succeeds when versions match."""
    await runner.upgrade_to_version("0005_exchange_rate_events_archive")

    # Should not raise
    await runner.validate_schema_version("0005_exchange_rate_events_archive")


@pytest.mark.asyncio
async def test_validate_schema_version_mismatch(runner):
    """validate_schema_version() raises VersionMismatchError when versions don't match."""
    await runner.upgrade_to_version("0005_exchange_rate_events_archive")

    with pytest.raises(
        VersionMismatchError,
        match="current=0005_exchange_rate_events_archive, expected=0008_add_account_aggregates",
    ):
        await runner.validate_schema_version("0008_add_account_aggregates")


@pytest.mark.asyncio
async def test_validate_schema_version_uninitialized(runner):
    """validate_schema_version() raises error for uninitialized database."""
    with pytest.raises(VersionMismatchError, match="current=None, expected=0001_initial"):
        await runner.validate_schema_version("0001_initial")

