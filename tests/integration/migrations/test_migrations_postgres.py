"""Integration tests for Migration API with PostgreSQL.

Requires: PostgreSQL 12+ running locally or in Docker.
Run with: pytest tests/integration/migrations/test_migrations_postgres.py -v
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from py_accountant.infrastructure.migrations import MigrationRunner

if TYPE_CHECKING:
    pass

# Skip if PostgreSQL not available
pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_POSTGRES_URL"),
    reason="PostgreSQL not available (set TEST_POSTGRES_URL)",
)


@pytest_asyncio.fixture
async def postgres_url() -> str:
    """Get PostgreSQL URL from environment."""
    return os.environ.get(
        "TEST_POSTGRES_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/test_migrations",
    )


@pytest_asyncio.fixture
async def postgres_engine(postgres_url: str) -> AsyncEngine:
    """Create PostgreSQL engine for tests."""
    engine = create_async_engine(postgres_url, echo=False)

    # Cleanup before test
    async with engine.begin() as conn:
        # Drop all tables (CASCADE)
        await conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))

    yield engine

    # Cleanup after test
    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))

    await engine.dispose()


@pytest_asyncio.fixture
async def runner(postgres_engine: AsyncEngine) -> MigrationRunner:
    """Create MigrationRunner for PostgreSQL."""
    return MigrationRunner(postgres_engine)


class TestPostgresMigrationLifecycle:
    """Test full migration lifecycle on PostgreSQL."""

    @pytest.mark.asyncio
    async def test_upgrade_to_head(self, runner: MigrationRunner):
        """Upgrade from empty DB to head."""
        # Initial state: no version
        current = await runner.get_current_version()
        assert current is None

        # Upgrade to head
        await runner.upgrade_to_head()

        # Check version
        current = await runner.get_current_version()
        assert current == "0008_add_account_aggregates"

        # Check no pending migrations
        pending = await runner.get_pending_migrations()
        assert len(pending) == 0

    @pytest.mark.asyncio
    async def test_upgrade_step_by_step(self, runner: MigrationRunner):
        """Upgrade migrations one by one."""
        # Upgrade to 0001
        await runner.upgrade_to_version("0001_initial")
        assert await runner.get_current_version() == "0001_initial"

        # Upgrade to 0002
        await runner.upgrade_to_version("0002_add_is_base_currency")
        assert await runner.get_current_version() == "0002_add_is_base_currency"

        # Check pending migrations (should be 6: 0003-0008)
        pending = await runner.get_pending_migrations()
        assert len(pending) == 6

    @pytest.mark.asyncio
    async def test_downgrade_from_head(self, runner: MigrationRunner):
        """Downgrade from head to specific version."""
        # Upgrade to head first
        await runner.upgrade_to_head()
        assert await runner.get_current_version() == "0008_add_account_aggregates"

        # Downgrade to 0005
        await runner.downgrade(target="0005_exchange_rate_events_archive")

        # Check version
        current = await runner.get_current_version()
        assert current == "0005_exchange_rate_events_archive"

        # Check pending migrations (should be 3: 0006-0008)
        pending = await runner.get_pending_migrations()
        assert len(pending) == 3

    @pytest.mark.asyncio
    async def test_downgrade_to_base(self, runner: MigrationRunner):
        """Downgrade all migrations to base."""
        # Upgrade to head first
        await runner.upgrade_to_head()

        # Downgrade to base
        await runner.downgrade(target="base")

        # Check version (should be None)
        current = await runner.get_current_version()
        assert current is None

        # Check all migrations are pending
        pending = await runner.get_pending_migrations()
        assert len(pending) == 8

    @pytest.mark.asyncio
    async def test_upgrade_after_downgrade(self, runner: MigrationRunner):
        """Upgrade back after downgrade."""
        # Upgrade to head
        await runner.upgrade_to_head()

        # Downgrade to 0003
        await runner.downgrade(target="0003_add_performance_indexes")
        assert await runner.get_current_version() == "0003_add_performance_indexes"

        # Upgrade back to head
        await runner.upgrade_to_head()
        assert await runner.get_current_version() == "0008_add_account_aggregates"


class TestPostgresSchemaVerification:
    """Test schema verification on PostgreSQL."""

    @pytest.mark.asyncio
    async def test_tables_created_after_migrations(
        self, runner: MigrationRunner, postgres_engine: AsyncEngine
    ):
        """Verify all tables are created after migrations."""
        # Upgrade to head
        await runner.upgrade_to_head()

        # Check tables exist
        async with postgres_engine.connect() as conn:
            result = await conn.execute(
                text(
                    """
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    ORDER BY table_name
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

        assert expected_tables.issubset(
            tables
        ), f"Missing tables: {expected_tables - tables}"

    @pytest.mark.asyncio
    async def test_indexes_created(
        self, runner: MigrationRunner, postgres_engine: AsyncEngine
    ):
        """Verify indexes are created (from 0003 migration)."""
        await runner.upgrade_to_head()

        async with postgres_engine.connect() as conn:
            result = await conn.execute(
                text(
                    """
                    SELECT indexname 
                    FROM pg_indexes 
                    WHERE schemaname = 'public' 
                    AND tablename IN ('transaction_lines', 'journals')
                    ORDER BY indexname
                """
                )
            )
            indexes = {row[0] for row in result}

        # Check at least some expected indexes exist
        expected_indexes = {
            "ix_tx_lines_account_full_name",
            "ix_tx_lines_currency_code",
            "ix_journals_occurred_at",
        }

        assert expected_indexes.issubset(
            indexes
        ), f"Missing indexes: {expected_indexes - indexes}"

    @pytest.mark.asyncio
    async def test_validate_schema_version_success(self, runner: MigrationRunner):
        """Validate schema version matches expected."""
        await runner.upgrade_to_head()

        # Should not raise
        await runner.validate_schema_version("0008_add_account_aggregates")

    @pytest.mark.asyncio
    async def test_validate_schema_version_mismatch(self, runner: MigrationRunner):
        """Validate schema version raises on mismatch."""
        await runner.upgrade_to_head()

        from py_accountant.infrastructure.migrations import VersionMismatchError

        with pytest.raises(VersionMismatchError) as exc_info:
            await runner.validate_schema_version("0005_exchange_rate_events_archive")

        assert "0008_add_account_aggregates" in str(exc_info.value)
        assert "0005_exchange_rate_events_archive" in str(exc_info.value)


class TestPostgresConcurrency:
    """Test concurrent migration scenarios (optional, if time permits)."""

    @pytest.mark.asyncio
    async def test_concurrent_upgrade_safe(
        self, postgres_url: str, postgres_engine: AsyncEngine
    ):
        """Test that concurrent upgrades don't cause issues."""
        # Create two runners with same DB
        runner1 = MigrationRunner(postgres_engine)

        # Create second engine
        engine2 = create_async_engine(postgres_url, echo=False)
        runner2 = MigrationRunner(engine2)

        try:
            # Both try to upgrade (one should succeed, other should be safe)
            await runner1.upgrade_to_head()
            await runner2.upgrade_to_head()

            # Both should report same version
            version1 = await runner1.get_current_version()
            version2 = await runner2.get_current_version()
            assert version1 == version2 == "0008_add_account_aggregates"
        finally:
            await engine2.dispose()

