"""E2E tests for Migration API CLI workflow.

Tests the full workflow as a user would experience it.
Run with: pytest tests/e2e/migrations/test_cli_workflow.py -v
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def temp_db_path(tmp_path: Path) -> Path:
    """Create temporary database path."""
    return tmp_path / "test_cli.db"


@pytest.fixture
def db_env(temp_db_path: Path) -> dict[str, str]:
    """Environment variables for CLI."""
    return {
        **os.environ.copy(),
        "DATABASE_URL": f"sqlite+aiosqlite:///{temp_db_path}",
    }


class TestCLIUpgradeWorkflow:
    """Test CLI upgrade workflow."""

    def test_upgrade_to_head_via_cli(self, db_env: dict[str, str]):
        """E2E: Upgrade to head via CLI."""
        result = subprocess.run(
            ["python", "-m", "py_accountant.infrastructure.migrations", "upgrade"],
            env=db_env,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "upgrade" in result.stdout.lower() or "success" in result.stdout.lower()

    def test_current_version_via_cli(self, db_env: dict[str, str]):
        """E2E: Check current version via CLI."""
        # Upgrade first
        subprocess.run(
            ["python", "-m", "py_accountant.infrastructure.migrations", "upgrade"],
            env=db_env,
            check=True,
            capture_output=True,
        )

        # Check current version
        result = subprocess.run(
            ["python", "-m", "py_accountant.infrastructure.migrations", "current"],
            env=db_env,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "0008" in result.stdout

    def test_pending_migrations_via_cli(self, db_env: dict[str, str]):
        """E2E: Check pending migrations via CLI."""
        # Don't upgrade - all should be pending
        result = subprocess.run(
            ["python", "-m", "py_accountant.infrastructure.migrations", "pending"],
            env=db_env,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        # Should show multiple pending migrations
        assert "0001" in result.stdout or "pending" in result.stdout.lower()

    def test_history_via_cli(self, db_env: dict[str, str]):
        """E2E: Check history via CLI."""
        result = subprocess.run(
            ["python", "-m", "py_accountant.infrastructure.migrations", "history"],
            env=db_env,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        # Should show migration history
        assert "0001" in result.stdout


class TestCLIDowngradeWorkflow:
    """Test CLI downgrade workflow."""

    def test_downgrade_via_cli(self, db_env: dict[str, str]):
        """E2E: Downgrade via CLI."""
        # Upgrade first
        subprocess.run(
            ["python", "-m", "py_accountant.infrastructure.migrations", "upgrade"],
            env=db_env,
            check=True,
            capture_output=True,
        )

        # Downgrade to 0005
        result = subprocess.run(
            [
                "python",
                "-m",
                "py_accountant.infrastructure.migrations",
                "downgrade",
                "0005",
            ],
            env=db_env,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0


class TestCLIErrorHandling:
    """Test CLI error handling."""

    def test_cli_without_database_url(self):
        """E2E: CLI without DATABASE_URL should fail gracefully."""
        env = os.environ.copy()
        env.pop("DATABASE_URL", None)
        env.pop("PYACC__DATABASE_URL", None)

        result = subprocess.run(
            ["python", "-m", "py_accountant.infrastructure.migrations", "upgrade"],
            env=env,
            capture_output=True,
            text=True,
        )

        assert result.returncode != 0
        assert "DATABASE_URL" in result.stderr or "DATABASE_URL" in result.stdout

    def test_cli_with_invalid_database_url(self):
        """E2E: CLI with invalid URL should fail gracefully."""
        env = {
            **os.environ.copy(),
            "DATABASE_URL": "invalid://url",
        }

        result = subprocess.run(
            ["python", "-m", "py_accountant.infrastructure.migrations", "upgrade"],
            env=env,
            capture_output=True,
            text=True,
        )

        assert result.returncode != 0


class TestCLIWithEcho:
    """Test CLI with --echo flag."""

    def test_upgrade_with_echo(self, db_env: dict[str, str]):
        """E2E: Upgrade with --echo shows SQL."""
        result = subprocess.run(
            [
                "python",
                "-m",
                "py_accountant.infrastructure.migrations",
                "upgrade",
                "--echo",
            ],
            env=db_env,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        # Should show SQL statements (CREATE TABLE, etc)
        # Note: output might be in stdout or stderr depending on logging
        output = result.stdout + result.stderr
        assert "CREATE TABLE" in output.upper() or "SQL" in output.upper()

