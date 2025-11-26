"""Alembic integration helpers."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from alembic.runtime.migration import MigrationContext

logger = logging.getLogger(__name__)


def include_in_alembic(
    context: MigrationContext,
    *,
    table_prefix: str = "",
    schema: str | None = None,
) -> None:
    """Include py_accountant migrations in external Alembic project.

    This function adds py_accountant's built-in migrations to the version
    locations of an external Alembic project, allowing them to be executed
    alongside the project's own migrations.

    Args:
        context: Alembic MigrationContext from env.py
        table_prefix: Optional prefix for py_accountant tables (e.g., "pyacc_")
        schema: Optional database schema for py_accountant tables

    Example:
        In your alembic/env.py:

        >>> from py_accountant.infrastructure.migrations import include_in_alembic
        >>>
        >>> def run_migrations_online():
        ...     with connectable.connect() as connection:
        ...         context.configure(connection=connection, target_metadata=target_metadata)
        ...         with context.begin_transaction():
        ...             include_in_alembic(context)
        ...             context.run_migrations()
    """
    # Graceful degradation if context doesn't have script
    if not hasattr(context, "script") or context.script is None:
        logger.warning(
            "Alembic context has no script directory, "
            "skipping py_accountant migrations integration"
        )
        return

    # Get path to py_accountant's versions directory
    versions_path = Path(__file__).parent / "versions"

    # Store original location and add py_accountant versions
    original_dir = context.script.dir

    # Initialize version_locations if not set
    if context.script.version_locations is None:
        context.script.version_locations = []

    # Convert to list if it's a tuple or other sequence
    if not isinstance(context.script.version_locations, list):
        context.script.version_locations = list(context.script.version_locations)

    # Add py_accountant versions first (to be applied before project migrations)
    context.script.version_locations.insert(0, str(versions_path))

    # Add original directory if not already present
    if original_dir not in context.script.version_locations:
        context.script.version_locations.append(original_dir)

    logger.info(
        "Included py_accountant migrations from %s "
        "(table_prefix=%r, schema=%r)",
        versions_path,
        table_prefix,
        schema,
    )


__all__ = [
    "include_in_alembic",
]

