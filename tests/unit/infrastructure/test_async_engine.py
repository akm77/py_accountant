from __future__ import annotations

import os

import pytest
from sqlalchemy import text

from py_accountant.infrastructure.persistence.sqlalchemy.async_engine import (
    get_async_engine,
    get_async_session_factory,
    normalize_async_url,
)


@pytest.mark.asyncio
async def test_async_engine_sqlite_connects_and_executes_select_1() -> None:
    """Smoke: ensure we can connect to SQLite in-memory and execute SELECT 1."""
    engine = get_async_engine("sqlite:///:memory:")  # will normalize to aiosqlite
    session_factory = get_async_session_factory(engine)

    async with engine.begin() as conn:
        # No schema creation is needed for SELECT 1
        res = await conn.execute(text("SELECT 1"))
        assert res.scalar() == 1

    # Also try via session
    async with session_factory() as session:
        res = await session.execute(text("SELECT 1"))
        assert res.scalar() == 1


@pytest.mark.parametrize(
    "input_url, expected",
    [
        ("postgresql://user@localhost/db", "postgresql+asyncpg://user@localhost/db"),
        ("postgresql+psycopg://u:p@h:5432/x", "postgresql+asyncpg://u:p@h:5432/x"),
        ("sqlite:///file.db", "sqlite+aiosqlite:///file.db"),
        ("sqlite+pysqlite:///:memory:", "sqlite+aiosqlite:///:memory:"),
        ("postgresql+asyncpg://user@h/db", "postgresql+asyncpg://user@h/db"),
        ("sqlite+aiosqlite:///./test.db", "sqlite+aiosqlite:///./test.db"),
    ],
)
def test_normalize_async_url(input_url: str, expected: str) -> None:
    assert normalize_async_url(input_url) == expected


@pytest.mark.asyncio
async def test_postgres_url_normalizes_but_connection_optional() -> None:
    """
    If a dev Postgres URL is provided via env (DATABASE_URL or DATABASE_URL_ASYNC),
    try a quick connect-then-dispose. This test is tolerant: it skips if no URL.
    """
    url = os.getenv("DATABASE_URL_ASYNC") or os.getenv("DATABASE_URL")
    if not url:
        pytest.skip("No DATABASE_URL(_ASYNC) provided in environment")

    engine = get_async_engine(url)
    try:
        async with engine.connect() as conn:
            res = await conn.execute(text("SELECT 1"))
            assert res.scalar() == 1
    finally:
        await engine.dispose()

