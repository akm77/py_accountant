"""Configuration for the Telegram bot example.

Iteration 1 implements a lean environment-based configuration loader without
external dependencies. Required environment variables:
- TELEGRAM_BOT_TOKEN
- DATABASE_URL (sync URL for migrations / reporting tools)
- DATABASE_URL_ASYNC (async URL for runtime operations)

Optional:
- LOG_LEVEL (default: INFO)
- AUDIT_LIMIT (default: 10, must be positive int; invalid/non-int => default)

Public API: `Settings` dataclass and `load_settings()` function.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

__all__ = ["Settings", "load_settings"]


@dataclass(slots=True)
class Settings:
    """Bot settings loaded from environment variables.

    Attributes:
        token: Telegram bot token (TELEGRAM_BOT_TOKEN).
        database_url_sync: Synchronous database URL (DATABASE_URL).
        database_url_async: Asynchronous database URL (DATABASE_URL_ASYNC).
        log_level: Logging level (LOG_LEVEL, default "INFO").
        audit_limit: Max number of audit events to display (/audit command).
    """

    token: str
    database_url_sync: str
    database_url_async: str
    log_level: str = "INFO"
    audit_limit: int = 10


def _get_env(name: str, *, required: bool = True, default: str | None = None) -> str:
    """Internal helper to fetch an environment variable.

    Args:
        name: Name of the environment variable.
        required: If True and value missing/empty, raises ValueError.
        default: Value used when variable is optional and not set.

    Returns:
        The environment value (str).

    Raises:
        ValueError: If required variable is missing.
    """
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        if required:
            raise ValueError(f"Missing env: {name}")
        return default if default is not None else ""
    return raw.strip()


def load_settings() -> Settings:
    """Load and validate bot settings from environment variables.

    Returns:
        Settings: Populated configuration dataclass.

    Raises:
        ValueError: If any required environment variable is missing.
    """
    token = _get_env("TELEGRAM_BOT_TOKEN", required=True)
    db_sync = _get_env("DATABASE_URL", required=True)
    db_async = _get_env("DATABASE_URL_ASYNC", required=True)

    log_level = _get_env("LOG_LEVEL", required=False, default="INFO") or "INFO"

    raw_limit = os.getenv("AUDIT_LIMIT", "").strip()
    audit_limit = 10
    if raw_limit:
        try:
            parsed = int(raw_limit)
            if parsed > 0:
                audit_limit = parsed
        except ValueError:  # noqa: BLE001
            # Ignore invalid AUDIT_LIMIT; keep default (lean – no logging here)
            pass

    return Settings(
        token=token,
        database_url_sync=db_sync,
        database_url_async=db_async,
        log_level=log_level or "INFO",
        audit_limit=audit_limit,
    )
