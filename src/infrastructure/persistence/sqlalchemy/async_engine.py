"""Async SQLAlchemy engine and session factory utilities.

This module introduces asynchronous database connectivity for runtime adapters,
without changing the existing synchronous UoW/Repositories (to be migrated in
subsequent iterations).

Key functions:
- normalize_async_url(url): ensure async driver is used (asyncpg/aiosqlite)
- get_async_engine(url, ...): create AsyncEngine with sane defaults
- get_async_session_factory(engine, ...): build async sessionmaker

Supported URL examples:
- PostgreSQL (async):
    postgresql+asyncpg://user:password@localhost:5432/mydb
  If a sync URL is passed, e.g. "postgresql://...", it's normalized to
  "postgresql+asyncpg://...".

- SQLite (async):
    sqlite+aiosqlite:///:memory:
    sqlite+aiosqlite:///./file.db
  If a sync URL is passed, e.g. "sqlite:///:memory:" or "sqlite+pysqlite:///file.db",
  it's normalized to the async scheme "sqlite+aiosqlite://...".

Notes:
- Alembic stays on sync URLs; do not use these helpers from migration code.
- UoW/Repositories remain synchronous in ASYNC-01; this module is a building block
  for future iterations.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from infrastructure.config.settings import get_settings

__all__ = [
    "normalize_async_url",
    "get_async_engine",
    "get_async_session_factory",
]


def normalize_async_url(url: str) -> str:
    """Normalize the given SQLAlchemy URL to an async-driver URL.

    Behavior:
    - postgresql://...           -> postgresql+asyncpg://...
    - postgresql+psycopg://...   -> postgresql+asyncpg://...
    - postgresql+psycopg2://...  -> postgresql+asyncpg://...
    - sqlite://...               -> sqlite+aiosqlite://...
    - sqlite+pysqlite://...      -> sqlite+aiosqlite://...
    - Already-async schemes (postgresql+asyncpg, sqlite+aiosqlite) are returned unchanged.

    Parameters:
    - url: Non-empty SQLAlchemy database URL string.

    Returns:
    - A URL string guaranteed to point to an async driver (asyncpg/aiosqlite) for
      supported backends (PostgreSQL/SQLite).

    Raises:
    - ValueError: if url is empty/whitespace.
    """
    if not url or not url.strip():
        raise ValueError("Database URL must be a non-empty string")

    sa_url = make_url(url)
    drivername = sa_url.drivername or ""

    # PostgreSQL family -> enforce asyncpg
    if drivername.startswith("postgresql") and drivername != "postgresql+asyncpg":
        sa_url = sa_url.set(drivername="postgresql+asyncpg")
        return sa_url.render_as_string(hide_password=False)

    # SQLite family -> enforce aiosqlite
    if drivername.startswith("sqlite") and drivername != "sqlite+aiosqlite":
        sa_url = sa_url.set(drivername="sqlite+aiosqlite")
        return sa_url.render_as_string(hide_password=False)

    # Unknown or already-async; return as-is
    return sa_url.render_as_string(hide_password=False)


def _engine_kwargs_for_dialect(norm_url: str, *, echo: bool, user_kwargs: dict[str, Any] | None) -> dict[str, Any]:
    """Build engine kwargs based on settings and target dialect.

    - For postgresql+asyncpg: apply pool sizing, timeouts, and connect_args(timeout)
    - For sqlite+aiosqlite: keep minimal; ignore pool options safely
    - For others: return minimal with pre_ping
    """
    settings = get_settings()
    sa_url = make_url(norm_url)
    drivername = sa_url.drivername
    extra = dict(user_kwargs or {})
    base: dict[str, Any] = {"echo": echo, "pool_pre_ping": True}

    if drivername.startswith("postgresql"):
        # Pool and timeouts
        base.update(
            {
                "pool_size": max(1, int(settings.db_pool_size)),
                "max_overflow": max(0, int(settings.db_max_overflow)),
                "pool_timeout": max(1, int(settings.db_pool_timeout)),
                "pool_recycle": max(0, int(settings.db_pool_recycle_sec)),
            }
        )
        # asyncpg connect timeout
        connect_timeout = max(1, int(settings.db_connect_timeout_sec))
        connect_args = dict(extra.pop("connect_args", {}))
        # asyncpg uses 'timeout' param for connect()
        connect_args.setdefault("timeout", connect_timeout)
        base["connect_args"] = connect_args
        # Merge user kwargs last to allow explicit override if needed
        base.update(extra)
        return base

    if drivername.startswith("sqlite"):
        # Keep minimal; sqlite pools behave differently, and options are often ignored
        base.update(extra)
        return base

    # Unknown driver: return minimal
    base.update(extra)
    return base


def get_async_engine(url: str, *, echo: bool = False, engine_kwargs: dict[str, Any] | None = None) -> AsyncEngine:
    """Create and return an AsyncEngine using the given URL.

    The URL is normalized to use async drivers for supported backends.

    Parameters:
    - url: Database URL (sync or async). Sync URLs are normalized to async.
    - echo: Enable SQL echo for debugging.
    - engine_kwargs: Extra keyword arguments forwarded to ``create_async_engine``.
      Useful keys may include pool settings (pool_size, max_overflow, etc.).
      If omitted, values are read from app settings (ENV) for supported dialects.

    Returns:
    - AsyncEngine instance.

    Example:
    >>> engine = get_async_engine("sqlite:///:memory:")  # normalized to aiosqlite
    >>> isinstance(engine, AsyncEngine)
    True
    """
    norm_url = normalize_async_url(url)
    kwargs = _engine_kwargs_for_dialect(norm_url, echo=echo, user_kwargs=engine_kwargs)

    engine: AsyncEngine = create_async_engine(
        norm_url,
        **kwargs,
    )
    return engine


def get_async_session_factory(
    engine: AsyncEngine,
    *,
    expire_on_commit: bool = False,
) -> async_sessionmaker[AsyncSession]:
    """Build an ``async_sessionmaker`` bound to the given ``AsyncEngine``.

    Parameters:
    - engine: AsyncEngine to bind sessions to.
    - expire_on_commit: Whether ORM instances should expire on commit.

    Returns:
    - ``async_sessionmaker[AsyncSession]`` instance for creating sessions::

        session_factory = get_async_session_factory(engine)
        async with session_factory() as session:
            ...  # use session

    Notes:
    - Tables are not auto-created here. Migrations and metadata management
      remain the responsibility of sync tooling (Alembic).
    """
    return async_sessionmaker(bind=engine, expire_on_commit=expire_on_commit, class_=AsyncSession)
