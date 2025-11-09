from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

EnvName = Literal["test", "production"]


class BaseAppSettings(BaseSettings):
    """Общие настройки приложения.

    Используется pydantic-settings для загрузки из ENV/.env.
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


class TestSettings(BaseAppSettings):
    """Тестовая среда.

    - Разрешает пустые небезопасные флаги по умолчанию
    - Поддерживает SQLite in-memory
    """

    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    # Значения по умолчанию для тестов
    env: EnvName = Field(default="test")
    database_url: str = Field(alias="DATABASE_URL", default="sqlite+pysqlite:///:memory:")
    log_level: str = Field(alias="LOG_LEVEL", default="DEBUG")
    json_logs: bool = Field(alias="JSON_LOGS", default=False)


class ProdSettings(BaseAppSettings):
    """Продакшен среда.

    Требует явного задания критичных переменных.
    """

    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    env: EnvName = Field(default="production")
    # database_url обязательно должно быть задано через ENV/секреты
    database_url: str = Field(alias="DATABASE_URL")
    log_level: str = Field(alias="LOG_LEVEL", default="INFO")
    json_logs: bool = Field(alias="JSON_LOGS", default=True)


# Классы без чтения .env для тестов изолированных профилей
class TestSettingsNoFile(TestSettings):
    model_config = SettingsConfigDict(env_file=(), extra="ignore")


class ProdSettingsNoFile(ProdSettings):
    model_config = SettingsConfigDict(env_file=(), extra="ignore")


@lru_cache(maxsize=8)
def get_settings(forced_env: EnvName | None = None, *, ignore_env_file: bool = False) -> BaseAppSettings:
    """Фабрика настроек на основе ENV с кэшированием.

    forced_env принудительно выбирает профиль и перекрывает значение ENV из окружения.
    ignore_env_file отключает чтение .env (используются классы *NoFile).
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
