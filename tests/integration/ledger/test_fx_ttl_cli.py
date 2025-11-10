from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from infrastructure.persistence.sqlalchemy.uow import SqlAlchemyUnitOfWork


def run_cli(args: list[str]) -> tuple[int, str]:
    import os
    import re
    import subprocess
    env = os.environ.copy()
    env.setdefault("LOG_LEVEL", "WARNING")  # reduce log noise in tests
    proc = subprocess.run(["python", "-m", "presentation.cli.main"] + args, capture_output=True, text=True, env=env)
    out = proc.stdout.strip()
    # remove ANSI escape codes and trailing log lines before JSON { start
    if "{" in out:
        json_start = out.find("{")
        out = out[json_start:]
    # strip ansi
    out = re.sub(r"\x1b\[[0-9;]*m", "", out)
    return (proc.returncode, out)


def test_fx_ttl_delete_mode_sqlite(tmp_path):
    db_url = f"sqlite+pysqlite:///{tmp_path}/fx_ttl.db"
    # Seed events via UoW for precise control of timestamps
    uow = SqlAlchemyUnitOfWork(db_url)
    now = datetime.now(UTC)
    old = now - timedelta(days=10)
    recent = now - timedelta(days=1)
    # Seed currency to satisfy CLI diagnostics if needed
    uow.currencies.upsert(type("D", (), {"code": "EUR", "exchange_rate": Decimal("1.1"), "is_base": False})())  # type: ignore
    uow.exchange_rate_events.add_event("EUR", Decimal("1.1"), old, policy_applied="none", source="test")
    uow.exchange_rate_events.add_event("EUR", Decimal("1.2"), recent, policy_applied="none", source="test")
    uow.commit()

    # Dry run should report affected=1 but not delete
    rc, out = run_cli(["--db-url", db_url, "maintenance:fx-ttl", "--mode", "delete", "--retention-days", "5", "--dry-run", "--json"])  # noqa: E501
    assert rc == 0
    data = json.loads(out)
    assert data["affected"] >= 1
    # Real run deletes
    rc, out = run_cli(["--db-url", db_url, "maintenance:fx-ttl", "--mode", "delete", "--retention-days", "5", "--json"])  # noqa: E501
    assert rc == 0
    data = json.loads(out)
    assert data["deleted"] >= 1


def test_fx_ttl_archive_mode_sqlite(tmp_path):
    db_url = f"sqlite+pysqlite:///{tmp_path}/fx_ttl_arch.db"
    uow = SqlAlchemyUnitOfWork(db_url)
    now = datetime.now(UTC)
    old = now - timedelta(days=10)
    uow.currencies.upsert(type("D", (), {"code": "EUR", "exchange_rate": Decimal("1.1"), "is_base": False})())  # type: ignore
    uow.exchange_rate_events.add_event("EUR", Decimal("1.1"), old, policy_applied="none", source="test")
    uow.commit()

    rc, out = run_cli(["--db-url", db_url, "maintenance:fx-ttl", "--mode", "archive", "--retention-days", "5", "--json"])  # noqa: E501
    assert rc == 0
    data = json.loads(out)
    assert data["archived"] == data["deleted"]
