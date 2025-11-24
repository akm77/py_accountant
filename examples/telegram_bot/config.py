"""Application configuration using pydantic-settings."""
from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Bot configuration loaded from environment variables.

    All py_accountant settings use PYACC__ prefix.
    Bot-specific settings use BOT_ prefix.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Telegram Bot
    bot_token: str = Field(..., alias="BOT_TOKEN")
    bot_log_level: str = Field("INFO", alias="BOT_LOG_LEVEL")
    bot_timezone: str = Field("UTC", alias="BOT_TIMEZONE")

    # py_accountant database URLs (dual-URL strategy)
    pyacc_database_url: str = Field(..., alias="PYACC__DATABASE_URL")
    pyacc_database_url_async: str = Field(..., alias="PYACC__DATABASE_URL_ASYNC")

    # py_accountant pool settings
    pyacc_db_pool_size: int = Field(20, alias="PYACC__DB_POOL_SIZE")
    pyacc_db_max_overflow: int = Field(10, alias="PYACC__DB_MAX_OVERFLOW")
    pyacc_db_pool_timeout: int = Field(30, alias="PYACC__DB_POOL_TIMEOUT")

    # py_accountant logging (should be disabled for bot)
    pyacc_logging_enabled: bool = Field(False, alias="PYACC__LOGGING_ENABLED")


# Singleton instance
settings = Settings()

