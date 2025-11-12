from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

PACKAGE_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "cli_fx.db"


def run_cli(args: list[str], db_path: Path, reset: bool = False) -> subprocess.CompletedProcess[str]:
    if reset and db_path.exists():
        db_path.unlink()
    env = {"DATABASE_URL_ASYNC": f"sqlite+aiosqlite:///{db_path}"}
    cmd = [sys.executable, "-m", "presentation.cli.main"] + args
    return subprocess.run(cmd, capture_output=True, text=True, cwd=str(PACKAGE_ROOT), env=env)


def prepare_base(db_path: Path) -> None:
    assert run_cli(["currency", "add", "USD"], db_path, reset=True).returncode == 0
    assert run_cli(["currency", "set-base", "USD"], db_path).returncode == 0


def test_cli_fx_add_event_and_list_json(db_path: Path):
    prepare_base(db_path)
    ts = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC).isoformat()
    add = run_cli(["fx", "add-event", "EUR", "1.100000", "--occurred-at", ts, "--source", "cli", "--json"], db_path)
    assert add.returncode == 0, add.stderr
    obj = json.loads(add.stdout)
    assert set(obj.keys()) == {"id", "code", "rate", "occurred_at", "policy_applied", "source"}
    assert obj["code"] == "EUR" and obj["rate"] == "1.100000" and obj["occurred_at"].startswith("2025-01-01T12:00:00")
    # List should include the event
    lst = run_cli(["fx", "list", "--json"], db_path)
    assert lst.returncode == 0, lst.stderr
    arr = json.loads(lst.stdout)
    assert isinstance(arr, list) and any(e["code"] == "EUR" for e in arr)


def test_cli_fx_add_event_invalid_code_raises(db_path: Path):
    prepare_base(db_path)
    proc = run_cli(["fx", "add-event", " ", "1.0"], db_path)
    assert proc.returncode == 2 and "[ERROR]" in proc.stderr


def test_cli_fx_add_event_invalid_rate_raises(db_path: Path):
    prepare_base(db_path)
    proc1 = run_cli(["fx", "add-event", "EUR", "abc"], db_path)
    assert proc1.returncode == 2 and "[ERROR]" in proc1.stderr
    proc2 = run_cli(["fx", "add-event", "EUR", "0"], db_path)
    assert proc2.returncode == 2 and "[ERROR]" in proc2.stderr


def test_cli_fx_list_filter_by_code(db_path: Path):
    prepare_base(db_path)
    # Add EUR and USD events
    ts = datetime(2025, 1, 1, 0, 0, 0, tzinfo=UTC).isoformat()
    assert run_cli(["fx", "add-event", "EUR", "1.1", "--occurred-at", ts], db_path).returncode == 0
    assert run_cli(["fx", "add-event", "USD", "1.0", "--occurred-at", ts], db_path).returncode == 0
    lst = run_cli(["fx", "list", "--code", "EUR", "--json"], db_path)
    assert lst.returncode == 0
    arr = json.loads(lst.stdout)
    assert all(e["code"] == "EUR" for e in arr)


def test_cli_fx_list_window_invalid_dates_raises(db_path: Path):
    prepare_base(db_path)
    proc = run_cli(["fx", "list", "--start", "2025-01-02T00:00:00", "--end", "2025-01-01T00:00:00"], db_path)
    assert proc.returncode == 2 and "[ERROR]" in proc.stderr


def test_cli_fx_ttl_plan_basic(db_path: Path):
    prepare_base(db_path)
    # Add old events
    old_ts = (datetime.now(UTC) - timedelta(days=10)).isoformat()
    assert run_cli(["fx", "add-event", "EUR", "1.2", "--occurred-at", old_ts], db_path).returncode == 0
    assert run_cli(["fx", "add-event", "EUR", "1.3", "--occurred-at", old_ts], db_path).returncode == 0
    plan = run_cli(["fx", "ttl-plan", "--retention-days", "0", "--batch-size", "10", "--json"], db_path)
    assert plan.returncode == 0, plan.stderr
    obj = json.loads(plan.stdout)
    for key in ["cutoff", "mode", "retention_days", "batch_size", "dry_run", "total_old", "batches", "old_event_ids"]:
        assert key in obj


def test_cli_fx_ttl_plan_invalid_params_raises(db_path: Path):
    prepare_base(db_path)
    assert run_cli(["fx", "ttl-plan", "--retention-days", "-1"], db_path).returncode == 2
    assert run_cli(["fx", "ttl-plan", "--batch-size", "0"], db_path).returncode == 2
    assert run_cli(["fx", "ttl-plan", "--mode", "bad"], db_path).returncode == 2

# Optional smoke tests

def test_cli_fx_list_pagination_limit_zero_empty(db_path: Path):
    prepare_base(db_path)
    assert run_cli(["fx", "add-event", "EUR", "1.1"], db_path).returncode == 0
    proc = run_cli(["fx", "list", "--limit", "0", "--json"], db_path)
    assert proc.returncode == 0
    assert proc.stdout.strip() == "[]"


def test_cli_fx_add_event_human_output_smoke(db_path: Path):
    prepare_base(db_path)
    proc = run_cli(["fx", "add-event", "EUR", "1.234567"], db_path)
    assert proc.returncode == 0 and proc.stdout.strip().startswith("FX event ")


def test_cli_fx_ttl_plan_human_output_smoke(db_path: Path):
    prepare_base(db_path)
    proc = run_cli(["fx", "ttl-plan"], db_path)
    assert proc.returncode == 0 and proc.stdout.strip().startswith("TTL cutoff=")

