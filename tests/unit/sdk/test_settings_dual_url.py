from __future__ import annotations

import pytest

from py_accountant.sdk.bootstrap import init_app
from py_accountant.sdk.settings import Settings, load_from_env, validate_dual_url


def test_only_async_url_ok():
    s = Settings(async_url="sqlite+aiosqlite:///:memory:")
    validate_dual_url(s)  # should not raise


def test_sync_and_async_pair_sqlite_ok():
    s = Settings(
        async_url="sqlite+aiosqlite:///./file.db",
        sync_url="sqlite+pysqlite:///./file.db",
    )
    validate_dual_url(s)  # should not raise


def test_sync_is_async_driver_raises():
    s = Settings(
        async_url="sqlite+aiosqlite:///./file.db",
        sync_url="sqlite+aiosqlite:///./file.db",
    )
    with pytest.raises(ValueError):
        validate_dual_url(s)


def test_async_is_sync_driver_raises():
    s = Settings(
        async_url="sqlite+pysqlite:///./file.db",
        sync_url="sqlite+pysqlite:///./file.db",
    )
    with pytest.raises(ValueError):
        validate_dual_url(s)


def test_mismatched_hosts_pg_raises():
    s = Settings(
        async_url="postgresql+asyncpg://u:p@localhost:5432/db1",
        sync_url="postgresql+psycopg://u:p@localhost:5432/db2",
    )
    with pytest.raises(ValueError):
        validate_dual_url(s)


def test_missing_both_urls_raises_in_init_app_when_use_env_true(monkeypatch: pytest.MonkeyPatch):
    # ensure no env leak from outside
    monkeypatch.delenv("DATABASE_URL_ASYNC", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ValueError):
        # init_app without settings, use_env=True -> load_from_env -> missing async url -> build_uow_factory fails
        init_app(use_env=True)


def test_namespaced_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PYACC__DATABASE_URL_ASYNC", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("PYACC__DATABASE_URL", "sqlite+pysqlite:///:memory:")
    settings = load_from_env()
    assert settings.async_url.startswith("sqlite+aiosqlite")
    assert settings.sync_url.startswith("sqlite+pysqlite")
