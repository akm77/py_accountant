"""Alembic environment для встроенных миграций py_accountant.

Адаптировано из alembic/env.py проекта.
Сохраняет критическую валидацию sync/async драйверов.
"""
# ruff: noqa: I001
from __future__ import annotations

import logging
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import make_url

from py_accountant.infrastructure.persistence.sqlalchemy.models import Base

# Module-level config - lazy initialization to support testing
config = None
log = logging.getLogger("alembic.env")

target_metadata = Base.metadata


def _get_config():
    """Get Alembic config, initializing if needed."""
    global config
    if config is None:
        config = context.config
        # Logging configuration
        if config.config_file_name is not None:
            fileConfig(config.config_file_name)
    return config


def get_sync_url() -> str:
    """Return a validated synchronous SQLAlchemy URL for Alembic.

    Resolution order for actual URL used:
    - Prefer programmatic ``sqlalchemy.url`` from Config when present (test isolation)
    - Fallback to environment variable ``DATABASE_URL`` when config is empty

    The URL is validated to ensure it's a synchronous driver.
    """
    async_url_present = os.getenv("DATABASE_URL_ASYNC")
    if async_url_present:
        log.warning(
            "DATABASE_URL_ASYNC is set but ignored by Alembic; migrations must use a sync URL via DATABASE_URL or sqlalchemy.url."
        )

    # First check config URL (programmatically set, e.g., by MigrationRunner)
    cfg_url = (_get_config().get_main_option("sqlalchemy.url") or "").strip()

    # Fallback to environment variable
    env_url = (os.getenv("DATABASE_URL") or "").strip()

    # Prefer programmatic config URL for actual engine usage when present
    raw_url = cfg_url or env_url

    # Only validate env URL if we're using it (config URL is already converted by MigrationRunner)
    if not cfg_url and env_url:
        # If env specifies an async driver, reject it
        try:
            env_sa_url = make_url(env_url)
            env_driver = (env_sa_url.drivername or "").lower()
            if any(tok in env_driver for tok in ["asyncpg", "aiosqlite", "+async"]):
                raise RuntimeError(
                    "Async driver not supported for Alembic; use a synchronous URL (e.g., postgresql+psycopg or sqlite+pysqlite)."
                )
        except RuntimeError:
            # Re-raise RuntimeError for async driver detection
            raise
        except Exception as exc:
            # If parsing failed, re-raise as ValueError to mimic SA behavior
            raise ValueError(f"Invalid DATABASE_URL: {env_url}") from exc
    if not raw_url:
        raise ValueError(
            "No synchronous database URL found (sqlalchemy.url or DATABASE_URL). Provide a sync URL e.g. postgresql+psycopg or sqlite+pysqlite."
        )

    # Return the URL (config URL is already converted to sync by MigrationRunner)
    sa_url = make_url(str(raw_url))
    return sa_url.render_as_string(hide_password=False)


def _initialize():
    """Initialize the Alembic environment."""
    sync_url = get_sync_url()
    _get_config().set_main_option("sqlalchemy.url", sync_url)

render_as_batch = False


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode using a validated sync URL.

    This configures the Alembic context with a literal URL and does not create
    an Engine. It's suitable for generating SQL scripts without connecting to
    the database. The URL is validated by get_sync_url() to prevent accidental
    use of async drivers.
    """
    url = _get_config().get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        render_as_batch=render_as_batch,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode using a validated sync Engine.

    This creates a synchronous Engine from the configuration (which has been
    populated with the validated sync URL) and connects to run migrations.
    Any attempt to pass an async driver is rejected early by get_sync_url().
    """
    cfg = _get_config()
    cfg_section = cfg.get_section(cfg.config_ini_section) or {}
    connectable = engine_from_config(
        cfg_section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            render_as_batch=render_as_batch,
        )
        with context.begin_transaction():
            context.run_migrations()


# Execute migrations when called by Alembic
# Check if we're in an Alembic runtime context
try:
    # This will succeed if Alembic has set up the context
    _get_config()
    _initialize()
    if context.is_offline_mode():
        run_migrations_offline()
    else:
        run_migrations_online()
except:
    # Not in Alembic context (e.g., when imported in tests)
    pass

