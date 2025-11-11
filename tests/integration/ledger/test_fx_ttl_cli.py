from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from presentation.async_bridge import add_exchange_rate_event_sync, create_currency_sync


def run_cli(args: list[str]) -> tuple[int, str]:
    import os
    import re
    import subprocess
    env = os.environ.copy()
    env.setdefault("LOG_LEVEL", "WARNING")
    proc = subprocess.run(["python", "-m", "presentation.cli.main"] + args, capture_output=True, text=True, env=env)
    out = proc.stdout.strip()
    if "{" in out:
        json_start = out.find("{")
        out = out[json_start:]
    out = re.sub(r"\x1b\[[0-9;]*m", "", out)
    return (proc.returncode, out)


def test_fx_ttl_delete_mode_sqlite(tmp_path, monkeypatch):
    db_url = f"sqlite+aiosqlite:///{tmp_path}/fx_ttl.db"
    # Seed events via bridge for precise timestamps in the same DB as CLI
    monkeypatch.setenv("DATABASE_URL", db_url)
    create_currency_sync("EUR", exchange_rate=Decimal("1.1"))
    now = datetime.now(UTC)
    old = now - timedelta(days=10)
    recent = now - timedelta(days=1)
    add_exchange_rate_event_sync("EUR", Decimal("1.1"), old, policy_applied="none", source="test")
    add_exchange_rate_event_sync("EUR", Decimal("1.2"), recent, policy_applied="none", source="test")

    rc, out = run_cli(["--db-url", db_url, "maintenance:fx-ttl", "--mode", "delete", "--retention-days", "5", "--dry-run", "--json"])  # noqa: E501
    assert rc == 0
    data = json.loads(out)
    assert data["affected"] >= 1
    rc, out = run_cli(["--db-url", db_url, "maintenance:fx-ttl", "--mode", "delete", "--retention-days", "5", "--json"])  # noqa: E501
    assert rc == 0
    data = json.loads(out)
    assert data["deleted"] >= 1


def test_fx_ttl_archive_mode_sqlite(tmp_path, monkeypatch):
    db_url = f"sqlite+aiosqlite:///{tmp_path}/fx_ttl_arch.db"
    monkeypatch.setenv("DATABASE_URL", db_url)
    create_currency_sync("EUR", exchange_rate=Decimal("1.1"))
    now = datetime.now(UTC)
    old = now - timedelta(days=10)
    add_exchange_rate_event_sync("EUR", Decimal("1.1"), old, policy_applied="none", source="test")

    rc, out = run_cli(["--db-url", db_url, "maintenance:fx-ttl", "--mode", "archive", "--retention-days", "5", "--json"])  # noqa: E501
    assert rc == 0
    data = json.loads(out)
    assert data["archived"] == data["deleted"]
