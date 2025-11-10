from sqlalchemy.engine import make_url


def test_dual_url_consistency():
    """Runtime async URL must use async driver, migrations sync URL must use sync driver.

    This is a lightweight check that the chosen example URLs conform to the policy.
    The Alembic env.py enforces sync-only for migrations; runtime async engine normalizes to async.
    """
    sync_url = "postgresql+psycopg://user:pass@localhost:5432/db"
    async_url = "postgresql+asyncpg://user:pass@localhost:5432/db"

    s = make_url(sync_url)
    a = make_url(async_url)

    assert "asyncpg" not in (s.drivername or "")
    assert "asyncpg" in (a.drivername or "")


def test_dual_url_can_be_different_strings():
    """Even when pointing to the same DB, driver segments should differ between runtime and migrations."""
    sync_url = "sqlite+pysqlite:///./db.sqlite3"
    async_url = "sqlite+aiosqlite:///./db.sqlite3"

    s = make_url(sync_url)
    a = make_url(async_url)

    assert s.drivername != a.drivername

