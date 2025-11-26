"""Migration error types."""

from __future__ import annotations


class MigrationError(Exception):
    """Base exception for migration errors."""

    pass


class VersionMismatchError(MigrationError):
    """Schema version does not match expected version."""

    pass


__all__ = [
    "MigrationError",
    "VersionMismatchError",
]

