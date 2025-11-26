"""Unit tests for migration errors."""

from __future__ import annotations

import pytest

from py_accountant.infrastructure.migrations.errors import (
    MigrationError,
    VersionMismatchError,
)


def test_migration_error_creation() -> None:
    """MigrationError can be created with a message."""
    error = MigrationError("test error")
    assert str(error) == "test error"
    assert isinstance(error, Exception)


def test_version_mismatch_error_creation() -> None:
    """VersionMismatchError can be created with a message."""
    error = VersionMismatchError("version mismatch")
    assert str(error) == "version mismatch"


def test_version_mismatch_inherits_migration_error() -> None:
    """VersionMismatchError inherits from MigrationError."""
    error = VersionMismatchError("test")
    assert isinstance(error, MigrationError)
    assert isinstance(error, Exception)


def test_migration_error_with_cause() -> None:
    """MigrationError can wrap another exception."""
    cause = ValueError("original error")
    error = MigrationError("wrapped error")
    error.__cause__ = cause

    assert str(error) == "wrapped error"
    assert error.__cause__ is cause


def test_version_mismatch_error_formatting() -> None:
    """VersionMismatchError formats version information."""
    current = "0005"
    expected = "0008"
    error = VersionMismatchError(
        f"Schema version mismatch: current={current}, expected={expected}"
    )

    assert "0005" in str(error)
    assert "0008" in str(error)
    assert "mismatch" in str(error).lower()

