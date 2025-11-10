# ruff: noqa: I001
from __future__ import annotations

import logging
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import make_url

from infrastructure.persistence.sqlalchemy.models import Base

# Alembic Config object
config = context.config

# Logging configuration
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

log = logging.getLogger("alembic.env")

target_metadata = Base.metadata


def get_sync_url() -> str:
    """Return a validated synchronous SQLAlchemy URL for Alembic.

    Resolution order:
    1) Environment variable DATABASE_URL (preferred)
    2) Config option sqlalchemy.url (fallback from alembic.ini or programmatic Config)

    Safety rules:
    - Warn and ignore DATABASE_URL_ASYNC for migrations.
    - Reject async drivers (asyncpg / aiosqlite).
    - Raise ValueError if neither source provides a URL.
    """
    async_url_present = os.getenv("DATABASE_URL_ASYNC")
    if async_url_present:
        log.warning(
            "DATABASE_URL_ASYNC is set but ignored by Alembic; migrations must use a sync URL via DATABASE_URL or sqlalchemy.url."
        )

    env_url = os.getenv("DATABASE_URL")
    cfg_url = config.get_main_option("sqlalchemy.url")
    raw_url = env_url or cfg_url
    if not raw_url or not raw_url.strip():
        raise ValueError(
            "No synchronous database URL found (DATABASE_URL or sqlalchemy.url). Provide a sync URL e.g. postgresql+psycopg or sqlite+pysqlite."
        )

    sa_url = make_url(str(raw_url))
    driver = (sa_url.drivername or "").lower()
    if any(tok in driver for tok in ["asyncpg", "aiosqlite", "+async"]):
        raise RuntimeError(
            "Async driver not supported for Alembic; use a synchronous DATABASE_URL/sqlalchemy.url (e.g., postgresql+psycopg or sqlite+pysqlite)."
        )
    return sa_url.render_as_string(hide_password=False)


SYNC_URL = get_sync_url()
config.set_main_option("sqlalchemy.url", SYNC_URL)

render_as_batch = False


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode using a validated sync URL.

    This configures the Alembic context with a literal URL and does not create
    an Engine. It's suitable for generating SQL scripts without connecting to
    the database. The URL is validated by get_sync_url() to prevent accidental
    use of async drivers.
    """
    url = config.get_main_option("sqlalchemy.url")
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
    cfg_section = config.get_section(config.config_ini_section) or {}
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


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
