from __future__ import annotations

from collections.abc import Generator
from contextlib import suppress

import pytest
from pydantic import ValidationError

from py_accountant.infrastructure.config.settings import BaseAppSettings, get_settings


@pytest.fixture(autouse=True)
def clear_env(monkeypatch: pytest.MonkeyPatch) -> Generator:
    # Сброс кэша настроек перед каждым тестом
    with suppress(Exception):
        get_settings.cache_clear()  # type: ignore[attr-defined]
    # Очистим переменные, которые могут мешать тестам
    for key in (
        "ENV",
        "DATABASE_URL",
        "LOG_LEVEL",
        "JSON_LOGS",
        "PYACC__DATABASE_URL",
        "PYACC__LOGGING_ENABLED",
        "PYACC__LOG_LEVEL",
        "LOGGING_ENABLED",
    ):
        monkeypatch.delenv(key, raising=False)
    yield


def test_settings_test_profile_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    # По умолчанию ENV=test, sqlite in-memory, DEBUG, JSON_LOGS=False
    s = get_settings(ignore_env_file=True)
    assert s.env == "test"
    assert s.database_url.startswith("sqlite+")
    assert s.log_level.upper() == "DEBUG"
    assert s.json_logs is False
    assert s.logging_enabled is True


def test_settings_prod_profile_requires_db_url(monkeypatch: pytest.MonkeyPatch) -> None:
    # Принудительно выбираем prod и игнорируем .env, чтобы не было DATABASE_URL
    with pytest.raises(ValidationError):
        _ = get_settings(forced_env="production", ignore_env_file=True)


def test_env_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost:5432/db")
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    monkeypatch.setenv("JSON_LOGS", "true")
    s: BaseAppSettings = get_settings(ignore_env_file=True)
    assert s.env == "production"
    assert s.database_url.startswith("postgresql+")
    assert s.log_level.upper() == "WARNING"
    assert s.json_logs is True


def test_forced_env_switch(monkeypatch: pytest.MonkeyPatch) -> None:
    # Принудительное переключение профиля игнорирует ENV и .env
    monkeypatch.setenv("ENV", "production")
    s = get_settings(forced_env="test", ignore_env_file=True)
    assert s.env == "test"


def test_namespaced_env_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PYACC__DATABASE_URL", "sqlite:///namespaced.db")
    monkeypatch.setenv("PYACC__LOG_LEVEL", "warning")
    s = get_settings(ignore_env_file=True)
    assert s.database_url.endswith("namespaced.db")
    assert s.log_level.upper() == "WARNING"


def test_logging_enabled_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOGGING_ENABLED", "false")
    s = get_settings(ignore_env_file=True)
    assert s.logging_enabled is False
