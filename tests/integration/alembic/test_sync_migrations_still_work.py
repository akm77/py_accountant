import os
import subprocess
import sys
from pathlib import Path

import pytest

BASE = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize(
    "db_url",
    [
        "sqlite+pysqlite:///:memory:",
        # File-based to ensure online mode with actual connection
        f"sqlite+pysqlite:///{(BASE / 'test_migrations.db').as_posix()}",
    ],
)
def test_sync_migrations_smoke(db_url: str, monkeypatch: pytest.MonkeyPatch):
    """Alembic should run upgrade/downgrade with a synchronous URL.

    This test sets DATABASE_URL (sync) and ensures that upgrade to head and downgrade to base
    complete without raising. We run Alembic as a module via subprocess to exercise the real CLI
    entrypoint and environment resolution from alembic/env.py.
    """
    env = os.environ.copy()
    env["DATABASE_URL"] = db_url

    # Upgrade to head
    proc_up = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BASE,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc_up.returncode == 0, f"alembic upgrade failed: {proc_up.stdout}\n{proc_up.stderr}"

    # Downgrade to base
    proc_down = subprocess.run(
        [sys.executable, "-m", "alembic", "downgrade", "base"],
        cwd=BASE,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc_down.returncode == 0, f"alembic downgrade failed: {proc_down.stdout}\n{proc_down.stderr}"


def test_alembic_rejects_async_url(monkeypatch: pytest.MonkeyPatch):
    """Passing an async driver in DATABASE_URL must cause env.py to fail early with RuntimeError."""
    env = os.environ.copy()
    env["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

    proc = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BASE,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode != 0, "alembic should fail when given async URL"
    assert "Async driver not supported for Alembic" in (proc.stderr + proc.stdout)

