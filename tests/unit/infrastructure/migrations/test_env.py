"""Unit tests for Alembic environment."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_alembic_config():
    """Mock Alembic config object for isolated testing."""
    mock_config = MagicMock()
    mock_config.get_main_option.return_value = None
    return mock_config


@pytest.fixture
def clean_env(monkeypatch):
    """Clean environment from database URL variables."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL_ASYNC", raising=False)


def test_get_sync_url_from_env_variable(monkeypatch, mock_alembic_config):
    """get_sync_url() reads DATABASE_URL from environment."""
    url = "postgresql+psycopg://user:pass@localhost/db"
    monkeypatch.setenv("DATABASE_URL", url)

    with patch('py_accountant.infrastructure.migrations.env._get_config', return_value=mock_alembic_config):
        from py_accountant.infrastructure.migrations.env import get_sync_url

        result = get_sync_url()

        assert "postgresql+psycopg" in result
        assert "localhost" in result


def test_get_sync_url_rejects_asyncpg(monkeypatch, mock_alembic_config):
    """get_sync_url() rejects postgresql+asyncpg driver."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://host/db")

    with patch('py_accountant.infrastructure.migrations.env._get_config', return_value=mock_alembic_config):
        from py_accountant.infrastructure.migrations.env import get_sync_url

        with pytest.raises(RuntimeError, match="Async driver not supported"):
            get_sync_url()


def test_get_sync_url_rejects_aiosqlite(monkeypatch, mock_alembic_config):
    """get_sync_url() rejects sqlite+aiosqlite driver."""
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///test.db")

    with patch('py_accountant.infrastructure.migrations.env._get_config', return_value=mock_alembic_config):
        from py_accountant.infrastructure.migrations.env import get_sync_url

        with pytest.raises(RuntimeError, match="Async driver not supported"):
            get_sync_url()


def test_get_sync_url_rejects_plus_async_suffix(monkeypatch, mock_alembic_config):
    """get_sync_url() rejects any driver with +async suffix."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+async://host/db")

    with patch('py_accountant.infrastructure.migrations.env._get_config', return_value=mock_alembic_config):
        from py_accountant.infrastructure.migrations.env import get_sync_url

        with pytest.raises(RuntimeError, match="Async driver not supported"):
            get_sync_url()


def test_get_sync_url_accepts_psycopg(monkeypatch, mock_alembic_config):
    """get_sync_url() accepts postgresql+psycopg driver."""
    url = "postgresql+psycopg://localhost/db"
    monkeypatch.setenv("DATABASE_URL", url)

    with patch('py_accountant.infrastructure.migrations.env._get_config', return_value=mock_alembic_config):
        from py_accountant.infrastructure.migrations.env import get_sync_url

        result = get_sync_url()

        assert "psycopg" in result
        assert "localhost" in result


def test_get_sync_url_accepts_sqlite_pysqlite(monkeypatch, mock_alembic_config):
    """get_sync_url() accepts sqlite+pysqlite driver."""
    url = "sqlite+pysqlite:///test.db"
    monkeypatch.setenv("DATABASE_URL", url)

    with patch('py_accountant.infrastructure.migrations.env._get_config', return_value=mock_alembic_config):
        from py_accountant.infrastructure.migrations.env import get_sync_url

        result = get_sync_url()

        assert "sqlite" in result
        assert "test.db" in result


def test_get_sync_url_accepts_plain_sqlite(monkeypatch, mock_alembic_config):
    """get_sync_url() accepts plain sqlite driver."""
    url = "sqlite:///test.db"
    monkeypatch.setenv("DATABASE_URL", url)

    with patch('py_accountant.infrastructure.migrations.env._get_config', return_value=mock_alembic_config):
        from py_accountant.infrastructure.migrations.env import get_sync_url

        result = get_sync_url()

        assert "sqlite" in result
        assert "test.db" in result


def test_get_sync_url_no_url_raises_error(clean_env, mock_alembic_config):
    """get_sync_url() raises ValueError when no URL provided."""
    with patch('py_accountant.infrastructure.migrations.env._get_config', return_value=mock_alembic_config):
        from py_accountant.infrastructure.migrations.env import get_sync_url

        with pytest.raises(ValueError, match="No synchronous database URL"):
            get_sync_url()


def test_get_sync_url_prefers_config_over_env(monkeypatch, mock_alembic_config):
    """get_sync_url() prefers programmatic config URL over environment."""
    env_url = "sqlite:///env.db"
    config_url = "sqlite:///config.db"

    monkeypatch.setenv("DATABASE_URL", env_url)
    mock_alembic_config.get_main_option.return_value = config_url

    with patch('py_accountant.infrastructure.migrations.env._get_config', return_value=mock_alembic_config):
        from py_accountant.infrastructure.migrations.env import get_sync_url

        result = get_sync_url()

        assert "config.db" in result


def test_get_sync_url_warns_about_async_url(monkeypatch, mock_alembic_config, caplog):
    """get_sync_url() warns when DATABASE_URL_ASYNC is set."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///test.db")
    monkeypatch.setenv("DATABASE_URL_ASYNC", "sqlite+aiosqlite:///test.db")

    with patch('py_accountant.infrastructure.migrations.env._get_config', return_value=mock_alembic_config):
        import logging

        # Ensure alembic.env logger is enabled
        logger = logging.getLogger("alembic.env")
        logger.setLevel(logging.WARNING)

        from py_accountant.infrastructure.migrations.env import get_sync_url

        with caplog.at_level(logging.WARNING, logger="alembic.env"):
            result = get_sync_url()

            assert "DATABASE_URL_ASYNC is set but ignored" in caplog.text
            assert "sqlite" in result


def test_get_sync_url_rejects_async_in_config_url(mock_alembic_config):
    """get_sync_url() rejects async driver in programmatic config URL."""
    config_url = "postgresql+asyncpg://host/db"
    mock_alembic_config.get_main_option.return_value = config_url

    with patch('py_accountant.infrastructure.migrations.env._get_config', return_value=mock_alembic_config):
        from py_accountant.infrastructure.migrations.env import get_sync_url

        with pytest.raises(RuntimeError, match="Async driver not supported"):
            get_sync_url()


def test_get_sync_url_invalid_url_raises_value_error(monkeypatch, mock_alembic_config):
    """get_sync_url() raises ValueError for invalid URL format."""
    monkeypatch.setenv("DATABASE_URL", "not-a-valid-url")

    with patch('py_accountant.infrastructure.migrations.env._get_config', return_value=mock_alembic_config):
        from py_accountant.infrastructure.migrations.env import get_sync_url

        with pytest.raises(ValueError, match="Invalid DATABASE_URL"):
            get_sync_url()

