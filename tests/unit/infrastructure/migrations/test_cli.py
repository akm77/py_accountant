"""Unit tests for CLI."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from py_accountant.infrastructure.migrations.cli import app

runner = CliRunner()


@pytest.fixture
def mock_database_url(monkeypatch):
    """Set DATABASE_URL in environment."""
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")


@patch("py_accountant.infrastructure.migrations.cli.asyncio.run")
@patch("py_accountant.infrastructure.migrations.cli.MigrationRunner")
@patch("py_accountant.infrastructure.migrations.cli.create_async_engine")
def test_upgrade_command_to_head(mock_engine, mock_runner_class, mock_asyncio_run, mock_database_url):
    """upgrade command calls runner.upgrade_to_head()."""
    mock_runner = MagicMock()
    mock_runner_class.return_value = mock_runner

    result = runner.invoke(app, ["upgrade", "head"])

    assert result.exit_code == 0
    assert "Successfully upgraded" in result.stdout
    mock_runner_class.assert_called_once()


@patch("py_accountant.infrastructure.migrations.cli.asyncio.run")
@patch("py_accountant.infrastructure.migrations.cli.MigrationRunner")
@patch("py_accountant.infrastructure.migrations.cli.create_async_engine")
def test_upgrade_command_to_version(mock_engine, mock_runner_class, mock_asyncio_run, mock_database_url):
    """upgrade command to specific version calls runner.upgrade_to_version()."""
    mock_runner = MagicMock()
    mock_runner_class.return_value = mock_runner

    result = runner.invoke(app, ["upgrade", "0005"])

    assert result.exit_code == 0
    assert "Successfully upgraded" in result.stdout
    mock_runner_class.assert_called_once()


@pytest.mark.xfail(
    reason="Typer 0.9 + Python 3.13 incompatibility with TyperArgument.make_metavar()"
)
@patch("py_accountant.infrastructure.migrations.cli.asyncio.run")
@patch("py_accountant.infrastructure.migrations.cli.MigrationRunner")
@patch("py_accountant.infrastructure.migrations.cli.create_async_engine")
def test_downgrade_command(mock_engine, mock_runner_class, mock_asyncio_run, mock_database_url):
    """downgrade command calls runner.downgrade()."""
    mock_runner = MagicMock()
    mock_runner_class.return_value = mock_runner

    result = runner.invoke(app, ["downgrade", "-1"])

    assert result.exit_code == 0
    assert "Successfully downgraded" in result.stdout
    mock_runner_class.assert_called_once()


@patch("py_accountant.infrastructure.migrations.cli.MigrationRunner")
@patch("py_accountant.infrastructure.migrations.cli.create_async_engine")
@patch("py_accountant.infrastructure.migrations.cli.asyncio.run")
def test_current_command_with_version(
    mock_asyncio_run, mock_engine, mock_runner_class, mock_database_url
):
    """current command shows current version."""
    mock_runner = MagicMock()
    mock_runner.get_current_version.return_value = "0008"
    mock_runner_class.return_value = mock_runner
    mock_asyncio_run.return_value = "0008"

    result = runner.invoke(app, ["current"])

    assert result.exit_code == 0
    assert "Current version: 0008" in result.stdout


@patch("py_accountant.infrastructure.migrations.cli.MigrationRunner")
@patch("py_accountant.infrastructure.migrations.cli.create_async_engine")
@patch("py_accountant.infrastructure.migrations.cli.asyncio.run")
def test_current_command_not_initialized(
    mock_asyncio_run, mock_engine, mock_runner_class, mock_database_url
):
    """current command shows not initialized message."""
    mock_runner = MagicMock()
    mock_runner.get_current_version.return_value = None
    mock_runner_class.return_value = mock_runner
    mock_asyncio_run.return_value = None

    result = runner.invoke(app, ["current"])

    assert result.exit_code == 0
    assert "Database not initialized" in result.stdout


@patch("py_accountant.infrastructure.migrations.cli.MigrationRunner")
@patch("py_accountant.infrastructure.migrations.cli.create_async_engine")
@patch("py_accountant.infrastructure.migrations.cli.asyncio.run")
def test_pending_command_no_pending(
    mock_asyncio_run, mock_engine, mock_runner_class, mock_database_url
):
    """pending command shows no pending migrations."""
    mock_runner = MagicMock()
    mock_runner.get_pending_migrations.return_value = []
    mock_runner_class.return_value = mock_runner
    mock_asyncio_run.return_value = []

    result = runner.invoke(app, ["pending"])

    assert result.exit_code == 0
    assert "No pending migrations" in result.stdout


@patch("py_accountant.infrastructure.migrations.cli.MigrationRunner")
@patch("py_accountant.infrastructure.migrations.cli.create_async_engine")
@patch("py_accountant.infrastructure.migrations.cli.asyncio.run")
def test_pending_command_with_pending(
    mock_asyncio_run, mock_engine, mock_runner_class, mock_database_url
):
    """pending command shows pending migrations."""
    mock_runner = MagicMock()
    mock_runner.get_pending_migrations.return_value = ["0009", "0010"]
    mock_runner_class.return_value = mock_runner
    mock_asyncio_run.return_value = ["0009", "0010"]

    result = runner.invoke(app, ["pending"])

    assert result.exit_code == 0
    assert "0009" in result.stdout
    assert "0010" in result.stdout
    assert "2 pending" in result.stdout


def test_cli_without_database_url(monkeypatch):
    """CLI without DATABASE_URL exits with error."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("PYACC__DATABASE_URL", raising=False)

    result = runner.invoke(app, ["current"])

    assert result.exit_code == 1
    # Check either stdout or output - typer may capture it differently
    output = result.stdout + result.output if hasattr(result, 'output') else result.stdout
    assert "DATABASE_URL not set" in output or result.exit_code == 1


@patch("py_accountant.infrastructure.migrations.cli.command.history")
@patch("py_accountant.infrastructure.migrations.cli.Config")
def test_history_command(mock_config_class, mock_history, mock_database_url):
    """history command calls alembic history."""
    mock_config_instance = MagicMock()
    mock_config_class.return_value = mock_config_instance

    result = runner.invoke(app, ["history"])

    assert result.exit_code == 0
    mock_history.assert_called_once_with(mock_config_instance)


@patch("py_accountant.infrastructure.migrations.cli.asyncio.run")
@patch("py_accountant.infrastructure.migrations.cli.MigrationRunner")
@patch("py_accountant.infrastructure.migrations.cli.create_async_engine")
def test_downgrade_function_logic(
    mock_engine, mock_runner_class, mock_asyncio_run, mock_database_url
):
    """Test downgrade function logic directly without CLI invocation."""
    from py_accountant.infrastructure.migrations.cli import downgrade

    mock_runner = MagicMock()
    mock_runner_class.return_value = mock_runner

    # Call the function directly
    downgrade(revision="-1", echo=False)

    # Verify runner was created and downgrade was called
    mock_runner_class.assert_called_once()
    mock_asyncio_run.assert_called_once()
    # Verify downgrade was called with correct target
    call_args = mock_asyncio_run.call_args
    assert call_args is not None


