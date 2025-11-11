"""Telegram bot example entry point (skeleton).

Iteration 0 placeholder. The real async bot logic (aiogram polling, handlers
registration) will be added in later iterations. For now this module only
provides an importable structure with a no-op main() to satisfy the RPG plan.
"""

from __future__ import annotations

import asyncio
import logging

from examples.telegram_bot.config import Settings, load_settings
from infrastructure.persistence.sqlalchemy.uow import AsyncSqlAlchemyUnitOfWork

__all__ = [
    "configure_logging",
    "create_uow",
    "main",
]


def _to_log_level(s: str) -> int:
    """Translate string level to logging constant, defaulting to INFO.

    Accepts common level names case-insensitively (DEBUG, INFO, WARNING,
    ERROR, CRITICAL). Any unknown or empty value falls back to INFO.
    """
    if not s:
        return logging.INFO
    name = s.strip().upper()
    mapping = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "WARN": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
        "FATAL": logging.CRITICAL,
    }
    return mapping.get(name, logging.INFO)


def configure_logging(level: str) -> logging.Logger:
    """Configure stdlib logging and return the application logger.

    Configures basicConfig with format "[LEVEL] message" and the provided
    level (unknown values default to INFO). Returns a named logger "bot".

    Args:
        level: Desired log level as a string.

    Returns:
        logging.Logger: A logger instance with the name "bot".
    """
    log_level = _to_log_level(level)
    logging.basicConfig(level=log_level, format="[%(levelname)s] %(message)s")
    logger = logging.getLogger("bot")
    logger.setLevel(log_level)
    return logger


def create_uow(settings: Settings) -> AsyncSqlAlchemyUnitOfWork:
    """Create and return AsyncSqlAlchemyUnitOfWork bound to async DB URL.

    The Unit of Work is initialized only with the asynchronous database URL
    from settings. No connections are opened at this point; resources are
    managed when the UoW is used as an async context manager.

    Args:
        settings: Loaded Settings containing database_url_async.

    Returns:
        AsyncSqlAlchemyUnitOfWork: Configured UoW instance.
    """
    return AsyncSqlAlchemyUnitOfWork(settings.database_url_async)


async def main() -> None:
    """Minimal app bootstrap for iteration 2.

    Loads settings from environment, configures logging, instantiates the
    async Unit of Work, logs an initialization message, and exits. Does not
    start the bot, open DB connections, or run migrations.
    """
    settings = load_settings()
    logger = configure_logging(settings.log_level)
    _ = create_uow(settings)
    logger.info("app_initialized")


if __name__ == "__main__":  # pragma: no cover - manual execution path
    asyncio.run(main())
