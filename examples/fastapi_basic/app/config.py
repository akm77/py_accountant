"""Application configuration using pydantic-settings."""
from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """FastAPI application settings.

    All py_accountant settings use PYACC__ prefix.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # FastAPI settings
    app_name: str = Field("Accounting API", alias="APP_NAME")
    debug: bool = Field(False, alias="DEBUG")

    # py_accountant database URL (async only for runtime)
    database_url_async: str = Field(..., alias="PYACC__DATABASE_URL_ASYNC")

    # Database pool settings
    db_pool_size: int = Field(20, alias="DB_POOL_SIZE")
    db_max_overflow: int = Field(10, alias="DB_MAX_OVERFLOW")
    db_pool_timeout: int = Field(30, alias="DB_POOL_TIMEOUT")


# Singleton instance
settings = Settings()

