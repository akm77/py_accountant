from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

EnvName = Literal["test", "production"]


class BaseAppSettings(BaseSettings):
    """
    Общие настройки приложения.

    Используется pydantic-settings для загрузки из ENV/.env.

    Также содержит параметры БД для async-стека (ASYNC-09):
    - Пул соединений и таймауты
    - Таймаут statement_timeout (PostgreSQL)
    - Параметры ретраев транзистентных ошибок
    """

    model_config = SettingsConfigDict(env_file=(".env",), env_file_encoding="utf-8", extra="ignore")

    # Поле env не связано напрямую с ENV, чтобы исключить коллизии и обеспечить явный контроль
    env: EnvName = Field(default="test")
    database_url: str = Field(alias="DATABASE_URL")
    log_level: str = Field(alias="LOG_LEVEL", default="INFO")
    json_logs: bool = Field(alias="JSON_LOGS", default=False)

    # Rotation options (used mainly when json_logs is true)
    log_file: str | None = Field(alias="LOG_FILE", default=None)
    log_rotation: Literal["time", "size"] = Field(alias="LOG_ROTATION", default="time")
    log_max_bytes: int = Field(alias="LOG_MAX_BYTES", default=10_485_760)  # 10 MiB
    log_backup_count: int = Field(alias="LOG_BACKUP_COUNT", default=7)
    log_rotate_when: str = Field(alias="LOG_ROTATE_WHEN", default="midnight")
    log_rotate_utc: bool = Field(alias="LOG_ROTATE_UTC", default=True)

    # Money and rate quantization/rounding settings (NS11)
    money_scale: int = Field(alias="MONEY_SCALE", default=2)
    rate_scale: int = Field(alias="RATE_SCALE", default=10)
    rounding: str = Field(alias="ROUNDING", default="ROUND_HALF_EVEN")  # name of decimal rounding constant

    # FX TTL / archival settings (NS20)
    fx_ttl_mode: Literal["none", "delete", "archive"] = Field(alias="FX_TTL_MODE", default="none")
    fx_ttl_retention_days: int = Field(alias="FX_TTL_RETENTION_DAYS", default=90)
    fx_ttl_batch_size: int = Field(alias="FX_TTL_BATCH_SIZE", default=1000)
    fx_ttl_dry_run: bool = Field(alias="FX_TTL_DRY_RUN", default=False)

    # ASYNC-09: Database pool/timeouts and retry settings (runtime async only)
    db_pool_size: int = Field(alias="DB_POOL_SIZE", default=5)
    db_max_overflow: int = Field(alias="DB_MAX_OVERFLOW", default=10)
    db_pool_timeout: int = Field(alias="DB_POOL_TIMEOUT", default=30)  # seconds
    db_pool_recycle_sec: int = Field(alias="DB_POOL_RECYCLE_SEC", default=1800)  # seconds
    db_connect_timeout_sec: int = Field(alias="DB_CONNECT_TIMEOUT_SEC", default=10)  # seconds
    db_statement_timeout_ms: int = Field(alias="DB_STATEMENT_TIMEOUT_MS", default=0)  # 0 -> disabled
    db_retry_attempts: int = Field(alias="DB_RETRY_ATTEMPTS", default=3)
    db_retry_backoff_ms: int = Field(alias="DB_RETRY_BACKOFF_MS", default=50)  # initial backoff in ms
    db_retry_max_backoff_ms: int = Field(alias="DB_RETRY_MAX_BACKOFF_MS", default=1000)  # cap in ms


class TestSettings(BaseAppSettings):
    """
    Тестовая среда.

    - Разрешает пустые небезопасные флаги по умолчанию
    - Поддерживает SQLite in-memory
    - Дефолты для пула/таймаутов/ретраев остаются консервативными
    """

    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    # Значения по умолчанию для тестов
    env: EnvName = Field(default="test")
    database_url: str = Field(alias="DATABASE_URL", default="sqlite+pysqlite:///:memory:")
    log_level: str = Field(alias="LOG_LEVEL", default="DEBUG")
    json_logs: bool = Field(alias="JSON_LOGS", default=False)


class ProdSettings(BaseAppSettings):
    """
    Продакшен среда.

    Требует явного задания критичных переменных.
    """

    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    env: EnvName = Field(default="production")
    # database_url обязательно должно быть задано через ENV/секреты; placeholder используется для статического анализа
    database_url: str = Field(alias="DATABASE_URL", default="__MISSING_DB_URL__")
    log_level: str = Field(alias="LOG_LEVEL", default="INFO")
    json_logs: bool = Field(alias="JSON_LOGS", default=True)

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """Ensure DATABASE_URL provided for production profile."""
        if v == "__MISSING_DB_URL__":
            raise ValueError("DATABASE_URL required")
        return v


# Классы без чтения .env для тестов изолированных профилей
class TestSettingsNoFile(TestSettings):
    model_config = SettingsConfigDict(env_file=(), extra="ignore")


class ProdSettingsNoFile(ProdSettings):
    model_config = SettingsConfigDict(env_file=(), extra="ignore")


@lru_cache(maxsize=8)
def get_settings(forced_env: EnvName | None = None, *, ignore_env_file: bool = False) -> BaseAppSettings:
    """
    Фабрика настроек на основе ENV с кэшированием.

    Parameters:
    - forced_env: Явно выбрать профиль ("test" или "production"), перекрывает ENV.
    - ignore_env_file: Отключить чтение .env (используются *NoFile классы).

    Returns:
    - Экземпляр настроек текущего окружения, включающий параметры БД/пула/ретраев для async стека.
    """
    import os

    selector: EnvName = forced_env or os.getenv("ENV", "test")  # type: ignore[assignment]
    if selector == "production":
        cls = ProdSettingsNoFile if ignore_env_file else ProdSettings
    else:
        cls = TestSettingsNoFile if ignore_env_file else TestSettings

    instance = cls()
    instance.env = selector  # гарантируем согласованность поля env с выбором профиля
    return instance
