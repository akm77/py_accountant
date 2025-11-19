"""SDK settings for runtime initialization (dual-URL validation).

This module provides a tiny Settings dataclass and helpers to load settings
from environment variables and validate a dual-URL setup used in this project:
- DATABASE_URL: sync URL for Alembic/migrations (psycopg/pysqlite)
- DATABASE_URL_ASYNC: async URL for runtime (asyncpg/aiosqlite)

Only PostgreSQL and SQLite backends are supported in this SDK layer.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from sqlalchemy.engine import make_url

__all__ = [
    "Settings",
    "load_from_env",
    "validate_dual_url",
]


def _env(name: str) -> str | None:
    prefixed = os.getenv(f"PYACC__{name}")
    if prefixed is not None and prefixed.strip() != "":
        return prefixed
    raw = os.getenv(name)
    if raw is not None and raw.strip() != "":
        return raw
    return None


def _env_snapshot() -> dict[str, str]:
    keys = ["DATABASE_URL_ASYNC", "DATABASE_URL"]
    snap: dict[str, str] = {}
    for key in keys:
        pref = f"PYACC__{key}"
        if pref in os.environ:
            snap[pref] = os.environ[pref]
        if key in os.environ:
            snap[key] = os.environ[key]
    return snap


@dataclass(slots=True)
class Settings:
    """Lightweight container for SDK initialization settings.

    Attributes:
        async_url: Runtime async database URL (asyncpg/aiosqlite) or None.
        sync_url: Migration sync database URL (psycopg/pysqlite) or None.
        env: Optional snapshot of environment variables used for diagnostics.
    """

    async_url: str | None = None
    sync_url: str | None = None
    env: dict[str, str] | None = None


# Driver families supported by this SDK
_POSTGRES_SYNC = {"postgresql", "postgresql+psycopg", "postgresql+psycopg2"}
_POSTGRES_ASYNC = {"postgresql+asyncpg"}
_SQLITE_SYNC = {"sqlite", "sqlite+pysqlite"}
_SQLITE_ASYNC = {"sqlite+aiosqlite"}
_SUPPORTED = _POSTGRES_SYNC | _POSTGRES_ASYNC | _SQLITE_SYNC | _SQLITE_ASYNC


def _drivername(url: str) -> str:
    return make_url(url).drivername


def _is_postgres(driver: str) -> bool:
    return driver.startswith("postgresql")


def _is_sqlite(driver: str) -> bool:
    return driver.startswith("sqlite")


def _is_async_driver(driver: str) -> bool:
    return driver in _POSTGRES_ASYNC or driver in _SQLITE_ASYNC


def _is_sync_driver(driver: str) -> bool:
    return driver in _POSTGRES_SYNC or driver in _SQLITE_SYNC


def load_from_env() -> Settings:
    """Load Settings from environment variables.

    Reads DATABASE_URL_ASYNC and DATABASE_URL. Empty values are treated as None.
    Returns a Settings instance with an env snapshot of the two keys (if present).
    """
    a = _env("DATABASE_URL_ASYNC")
    s = _env("DATABASE_URL")
    env_snapshot = _env_snapshot()
    return Settings(async_url=a, sync_url=s, env=env_snapshot)


def validate_dual_url(settings: Settings) -> None:
    """Validate pair of sync/async URLs according to project policy.

    Rules:
    - If async_url is provided: it must use an async driver (asyncpg/aiosqlite) and be a
      PostgreSQL or SQLite URL.
    - If sync_url is provided: it must use a sync driver (psycopg/pysqlite) and be PostgreSQL/SQLite.
    - If both are provided: they must point to the same database (same dialect and same
      host/port/database or same SQLite file). Differences in driver names are expected.
    - If only sync_url is provided: validation passes (init_app may still require async_url).

    Raises:
        ValueError: if any rule is violated or an unsupported scheme is used.
    """
    async_url = settings.async_url
    sync_url = settings.sync_url

    # Validate async side
    if async_url:
        adrv = _drivername(async_url)
        if adrv not in _SUPPORTED:
            raise ValueError("Unsupported database scheme in async_url (only PostgreSQL/SQLite)")
        if not _is_async_driver(adrv):
            raise ValueError("async_url must use an async driver (asyncpg or aiosqlite)")
        if not (_is_postgres(adrv) or _is_sqlite(adrv)):
            raise ValueError("async_url must be PostgreSQL or SQLite")

    # Validate sync side
    if sync_url:
        sdrv = _drivername(sync_url)
        if sdrv not in _SUPPORTED:
            raise ValueError("Unsupported database scheme in sync_url (only PostgreSQL/SQLite)")
        if not _is_sync_driver(sdrv):
            raise ValueError("sync_url must use a sync driver (psycopg or pysqlite)")
        if not (_is_postgres(sdrv) or _is_sqlite(sdrv)):
            raise ValueError("sync_url must be PostgreSQL or SQLite")

    # If both provided: ensure they point to the same DB
    if async_url and sync_url:
        a = make_url(async_url)
        s = make_url(sync_url)
        # Dialect (postgresql/sqlite) must match
        if (_is_postgres(a.drivername) and not _is_postgres(s.drivername)) or (
            _is_sqlite(a.drivername) and not _is_sqlite(s.drivername)
        ):
            raise ValueError("runtime and migration URLs target different dialects (PostgreSQL vs SQLite)")

        if _is_postgres(a.drivername):
            # Compare host/port/database
            if (a.host or "localhost") != (s.host or "localhost") or (a.port or 5432) != (s.port or 5432) or (a.database or "") != (s.database or ""):
                raise ValueError(
                    "runtime and migration URL point to different PostgreSQL databases; check DATABASE_URL and DATABASE_URL_ASYNC"
                )
        else:  # sqlite
            # Compare database path; treat in-memory as equivalent
            a_db = (a.database or "").strip()
            s_db = (s.database or "").strip()
            a_mem = a_db == ":memory:"
            s_mem = s_db == ":memory:"
            if a_mem and s_mem:
                return None
            if a_db == s_db:
                return None
            raise ValueError(
                "runtime and migration URL point to different SQLite files; check DATABASE_URL and DATABASE_URL_ASYNC"
            )

    # If only sync provided: pass (bootstrap may still enforce async for runtime)
    return None

