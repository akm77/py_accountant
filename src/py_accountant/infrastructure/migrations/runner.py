"""Programmatic API for py_accountant database migrations."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from alembic import command

if TYPE_CHECKING:
    from alembic.script import ScriptDirectory

logger = logging.getLogger(__name__)


class MigrationRunner:
    """Programmatic API for py_accountant database migrations.

    Examples:
        runner = MigrationRunner(engine)
        await runner.upgrade_to_head()
    """

    def __init__(
        self,
        engine: AsyncEngine,
        *,
        alembic_config_path: str | Path | None = None,
        echo: bool = False,
    ):
        """Initialize migration runner.

        Args:
            engine: AsyncEngine for database operations
            alembic_config_path: Path to alembic.ini (optional)
            echo: Enable SQL echo (default: False)
        """
        self.engine = engine
        self.echo = echo
        self._config = self._load_alembic_config(alembic_config_path)

    def _load_alembic_config(self, config_path: str | Path | None) -> Config:
        """Load Alembic configuration.

        Args:
            config_path: Path to alembic.ini or None to use default

        Returns:
            Configured Alembic Config instance
        """
        if config_path is None:
            # Use the migrations directory as script location
            migrations_dir = Path(__file__).parent
            # Create a minimal config in memory
            config = Config()
            config.set_main_option("script_location", str(migrations_dir))
        else:
            config = Config(str(config_path))
            migrations_dir = Path(__file__).parent
            config.set_main_option("script_location", str(migrations_dir))

        # Set SQLAlchemy URL from engine - convert async drivers to sync
        url_str = self.engine.url.render_as_string(hide_password=False)
        # Convert async drivers to sync equivalents for Alembic
        url_str = url_str.replace("sqlite+aiosqlite", "sqlite")
        url_str = url_str.replace("postgresql+asyncpg", "postgresql+psycopg")
        config.set_main_option("sqlalchemy.url", url_str)

        return config

    async def upgrade_to_head(self) -> None:
        """Apply all pending migrations to head."""
        await self._run_in_sync(lambda: command.upgrade(self._config, "head"))
        logger.info("Successfully upgraded to head")

    async def upgrade_to_version(self, version: str) -> None:
        """Apply migrations to specific version.

        Args:
            version: Revision ID (e.g., "0005")
        """
        await self._run_in_sync(lambda: command.upgrade(self._config, version))
        logger.info(f"Successfully upgraded to version {version}")

    async def downgrade(self, *, steps: int = 1, target: str | None = None) -> None:
        """Downgrade migrations.

        Args:
            steps: Number of steps to downgrade (if target is None)
            target: Target revision or "base" for full downgrade
        """
        if target is None:
            target = f"-{steps}"

        await self._run_in_sync(lambda: command.downgrade(self._config, target))
        logger.info(f"Successfully downgraded to {target}")

    async def get_current_version(self) -> str | None:
        """Get current schema version from database.

        Returns:
            Revision ID or None if database not initialized
        """
        async with self.engine.connect() as conn:
            try:
                result = await conn.execute(
                    text("SELECT version_num FROM alembic_version LIMIT 1")
                )
                row = result.first()
                return row[0] if row else None
            except Exception:
                # Table doesn't exist yet
                return None

    async def get_pending_migrations(self) -> list[str]:
        """Get list of pending migrations.

        Returns:
            List of revision IDs not yet applied
        """
        from alembic.script import ScriptDirectory as SD

        script: ScriptDirectory = SD.from_config(self._config)
        current = await self.get_current_version()

        if current is None:
            # Database not initialized, all migrations are pending
            return [rev.revision for rev in script.walk_revisions()]

        # Get pending between current and head (iterate from head down to current)
        pending = []
        for rev in script.iterate_revisions("head", current):
            if rev.revision != current:
                pending.append(rev.revision)

        return pending

    async def validate_schema_version(self, expected: str) -> None:
        """Validate schema version matches expected.

        Args:
            expected: Expected schema version

        Raises:
            VersionMismatchError: If versions don't match
        """
        from .errors import VersionMismatchError

        current = await self.get_current_version()
        if current != expected:
            raise VersionMismatchError(
                f"Schema version mismatch: current={current}, expected={expected}"
            )

    async def _run_in_sync(self, func):
        """Run synchronous Alembic command via asyncio.

        Args:
            func: Synchronous function to execute
        """
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, func)


__all__ = ["MigrationRunner"]

