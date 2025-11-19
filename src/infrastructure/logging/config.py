from __future__ import annotations

import logging
import logging.handlers
import sys
from typing import IO, Any

import structlog

from infrastructure.config.settings import get_settings


def _resolve_level(level_name: str) -> int:
    """Return logging level from name with safe fallback to INFO."""
    try:
        return getattr(logging, level_name.upper())
    except Exception:
        return logging.INFO


def configure_logging(stream: IO[str] | None = None) -> None:
    """Initialize structlog + stdlib logging for console or JSON rendering.

    Best practices applied:
    - One or two handlers: stdout for console or when no file; rotating file for JSON if LOG_FILE set
    - Contextvars merged; timestamp ISO; level and logger name added
    - JSON vs human-friendly console based on settings.json_logs
    - Force reconfigure to avoid duplicate handlers between tests/runs

    stream: optional text stream for console handler (defaults to sys.stdout).
    """
    settings = get_settings()
    if not settings.logging_enabled:
        logging.basicConfig(handlers=[], level=logging.CRITICAL, force=True)
        structlog.configure(cache_logger_on_first_use=True)
        return
    level_value = _resolve_level(settings.log_level)

    # Common processors used in both stdlib pre-chain and structlog chain
    timestamper = structlog.processors.TimeStamper(fmt="iso")
    pre_chain: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        timestamper,
    ]

    # Select renderer according to settings
    if settings.json_logs:
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    handlers: list[logging.Handler] = []

    if settings.json_logs and settings.log_file:
        # File rotation in JSON mode
        if settings.log_rotation == "size":
            fh: logging.Handler = logging.handlers.RotatingFileHandler(
                filename=settings.log_file,
                maxBytes=max(1024, settings.log_max_bytes),
                backupCount=max(1, settings.log_backup_count),
                encoding="utf-8",
            )
        else:
            # time-based, default at midnight
            fh = logging.handlers.TimedRotatingFileHandler(
                filename=settings.log_file,
                when=settings.log_rotate_when,
                interval=1,
                backupCount=max(1, settings.log_backup_count),
                utc=settings.log_rotate_utc,
                encoding="utf-8",
            )
        fh.setFormatter(
            structlog.stdlib.ProcessorFormatter(
                processor=renderer,
                foreign_pre_chain=pre_chain,
            )
        )
        handlers.append(fh)
    else:
        # Console/stdout handler (or provided stream)
        sh = logging.StreamHandler(stream or sys.stdout)
        sh.setFormatter(
            structlog.stdlib.ProcessorFormatter(
                processor=renderer,
                foreign_pre_chain=pre_chain,
            )
        )
        handlers.append(sh)

    logging.basicConfig(handlers=handlers, level=level_value, force=True)

    # Configure structlog itself to hand events to ProcessorFormatter.
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            timestamper,  # ensure timestamp for structlog-originated records
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,  # type: ignore[arg-type]
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = "app") -> structlog.BoundLogger:
    """Return a structured logger; configure on first use if needed."""
    if not logging.getLogger().handlers:
        settings = get_settings()
        if settings.logging_enabled:
            configure_logging()
        else:
            logging.basicConfig(handlers=[], level=logging.CRITICAL, force=True)
    return structlog.get_logger(name)
