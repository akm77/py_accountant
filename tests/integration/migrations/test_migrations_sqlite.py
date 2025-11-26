"""Integration tests for Migration API with SQLite.

SQLite tests run without external dependencies.
Run with: pytest tests/integration/migrations/test_migrations_sqlite.py -v
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from py_accountant.infrastructure.migrations import MigrationRunner

if TYPE_CHECKING:
    pass


@pytest_asyncio.fixture
async def sqlite_file_engine(tmp_path: Path) -> AsyncEngine:
    """Create file-based SQLite engine for tests."""
    db_path = tmp_path / "test_migrations.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", echo=False)

    yield engine

    await engine.dispose()


@pytest_asyncio.fixture
async def sqlite_memory_engine() -> AsyncEngine:
    """Create in-memory SQLite engine for tests."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    yield engine

    await engine.dispose()


@pytest_asyncio.fixture
async def sqlite_runner(sqlite_file_engine: AsyncEngine) -> MigrationRunner:
    """Create MigrationRunner for file-based SQLite."""
    return MigrationRunner(sqlite_file_engine)


class TestSQLiteMigrationLifecycle:
    """Test full migration lifecycle on SQLite."""

    @pytest.mark.asyncio
    async def test_upgrade_to_head_file_based(self, sqlite_runner: MigrationRunner):
        """Upgrade to head on file-based SQLite."""
        # Upgrade to head
        await sqlite_runner.upgrade_to_head()

        # Check version
        current = await sqlite_runner.get_current_version()
        assert current == "0008_add_account_aggregates"

    @pytest.mark.asyncio
    @pytest.mark.xfail(
        reason="In-memory SQLite doesn't persist across Alembic's internal connections"
    )
    async def test_upgrade_to_head_in_memory(self, sqlite_memory_engine: AsyncEngine):
        """Upgrade to head on in-memory SQLite.

        Note: This test is marked as xfail because Alembic creates separate
        connections for migrations, and in-memory SQLite doesn't persist
        across connections. Use file-based SQLite for testing.
        """
        runner = MigrationRunner(sqlite_memory_engine)

        # Upgrade to head
        await runner.upgrade_to_head()

        # Check version
        current = await runner.get_current_version()
        assert current == "0008_add_account_aggregates"

    @pytest.mark.asyncio
    async def test_downgrade_and_upgrade_sqlite(self, sqlite_runner: MigrationRunner):
        """Test downgrade and upgrade cycle on SQLite."""
        # Upgrade to head
        await sqlite_runner.upgrade_to_head()

        # Downgrade to 0004
        await sqlite_runner.downgrade(target="0004_add_exchange_rate_events")
        assert (
            await sqlite_runner.get_current_version()
            == "0004_add_exchange_rate_events"
        )

        # Upgrade back to head
        await sqlite_runner.upgrade_to_head()
        assert await sqlite_runner.get_current_version() == "0008_add_account_aggregates"

    @pytest.mark.asyncio
    async def test_migration_persistence_across_connections(self, tmp_path: Path):
        """Test that migrations persist across connections (file-based)."""
        db_path = tmp_path / "persistent.db"
        url = f"sqlite+aiosqlite:///{db_path}"

        # First connection: upgrade
        engine1 = create_async_engine(url, echo=False)
        runner1 = MigrationRunner(engine1)
        await runner1.upgrade_to_head()
        await engine1.dispose()

        # Second connection: check version
        engine2 = create_async_engine(url, echo=False)
        runner2 = MigrationRunner(engine2)
        current = await runner2.get_current_version()
        assert current == "0008_add_account_aggregates"
        await engine2.dispose()


class TestSQLiteSchemaVerification:
    """Test schema verification on SQLite."""

    @pytest.mark.asyncio
    async def test_tables_created_sqlite(
        self, sqlite_runner: MigrationRunner, sqlite_file_engine: AsyncEngine
    ):
        """Verify all tables are created on SQLite."""
        await sqlite_runner.upgrade_to_head()

        async with sqlite_file_engine.connect() as conn:
            result = await conn.execute(
                text(
                    """
                    SELECT name 
                    FROM sqlite_master 
                    WHERE type='table' 
                    ORDER BY name
                """
                )
            )
            tables = {row[0] for row in result}

        expected_tables = {
            "alembic_version",
            "currencies",
            "accounts",
            "journals",
            "transaction_lines",
            "exchange_rate_events",
            "exchange_rate_events_archive",
            "account_balances",
            "account_daily_turnovers",
        }

        assert expected_tables.issubset(tables)

    @pytest.mark.asyncio
    async def test_indexes_created_sqlite(
        self, sqlite_runner: MigrationRunner, sqlite_file_engine: AsyncEngine
    ):
        """Verify indexes are created on SQLite."""
        await sqlite_runner.upgrade_to_head()

        async with sqlite_file_engine.connect() as conn:
            result = await conn.execute(
                text(
                    """
                    SELECT name 
                    FROM sqlite_master 
                    WHERE type='index' 
                    AND sql IS NOT NULL
                    ORDER BY name
                """
                )
            )
            indexes = {row[0] for row in result}

        # Check at least some indexes exist
        expected_indexes = {
            "ix_tx_lines_account_full_name",
            "ix_tx_lines_currency_code",
            "ix_journals_occurred_at",
        }

        assert expected_indexes.issubset(indexes)

    @pytest.mark.asyncio
    async def test_validate_schema_version_sqlite(self, sqlite_runner: MigrationRunner):
        """Validate schema version on SQLite."""
        await sqlite_runner.upgrade_to_head()

        # Should not raise
        await sqlite_runner.validate_schema_version("0008_add_account_aggregates")


class TestSQLiteURLConversion:
    """Test URL conversion (aiosqlite → sqlite)."""

    @pytest.mark.asyncio
    async def test_aiosqlite_url_converted(self, tmp_path: Path):
        """Test that aiosqlite:// URL is converted to sqlite:// for Alembic."""
        db_path = tmp_path / "test.db"

        # Create engine with aiosqlite
        async_url = f"sqlite+aiosqlite:///{db_path}"
        engine = create_async_engine(async_url, echo=False)

        runner = MigrationRunner(engine)

        # Upgrade should work (URL converted internally)
        await runner.upgrade_to_head()

        # Check version
        current = await runner.get_current_version()
        assert current == "0008_add_account_aggregates"

        await engine.dispose()

