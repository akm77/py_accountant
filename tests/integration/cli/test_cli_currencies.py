from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

PACKAGE_ROOT = Path(__file__).resolve().parents[3]

# --- Helpers & Fixtures ---
@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    """Return per-test sqlite file path (not created until first command).

    Each test gets a unique temporary directory; using a single file inside it
    guarantees isolation without manual deletion flags. For a "fresh" state in
    the middle of a test, remove the file explicitly (db_path.unlink()).
    """
    return tmp_path / "cli_test.db"


def run_cli(args: list[str], db_path: Path, reset: bool = False) -> subprocess.CompletedProcess[str]:
    """Run CLI command in a subprocess against provided DB file.

    Args:
        args: CLI argument list (excluding module invocation).
        db_path: SQLite file path (async aiosqlite URL built from it).
        reset: When True removes existing DB file before running command.
    Returns:
        CompletedProcess with captured output.
    """
    if reset and db_path.exists():
        db_path.unlink()
    env = {}
    env.update({"DATABASE_URL_ASYNC": f"sqlite+aiosqlite:///{db_path}"})
    cmd = [sys.executable, "-m", "presentation.cli.main"] + args
    return subprocess.run(cmd, capture_output=True, text=True, cwd=str(PACKAGE_ROOT), env=env)

# --- Tests ---

def test_cli_currency_list_empty_returns_empty_json(db_path: Path):
    proc = run_cli(["currency", "list", "--json"], db_path, reset=True)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "[]"


def test_cli_currency_add_list_json(db_path: Path):
    add_proc = run_cli(["currency", "add", "USD", "--json"], db_path, reset=True)
    assert add_proc.returncode == 0, add_proc.stderr
    added = json.loads(add_proc.stdout)
    assert added["code"] == "USD"
    assert added["is_base"] is False
    list_proc = run_cli(["currency", "list", "--json"], db_path)
    assert list_proc.returncode == 0, list_proc.stderr
    data = json.loads(list_proc.stdout)
    assert len(data) == 1 and data[0]["code"] == "USD"
    assert data[0]["is_base"] is False and data[0]["exchange_rate"] is None


def test_cli_currency_add_with_rate_and_human_output(db_path: Path):
    proc = run_cli(["currency", "add", "EUR", "--rate", "1.2345"], db_path, reset=True)
    assert proc.returncode == 0, proc.stderr
    line = proc.stdout.strip()
    assert line.startswith("Currency EUR base=False rate=")
    assert re.search(r"1\.2345(00)?$", line), line


def test_cli_currency_set_base(db_path: Path):
    assert run_cli(["currency", "add", "USD"], db_path, reset=True).returncode == 0
    assert run_cli(["currency", "add", "EUR", "--rate", "1.2500"], db_path).returncode == 0
    proc = run_cli(["currency", "set-base", "USD", "--json"], db_path)
    assert proc.returncode == 0, proc.stderr
    arr = json.loads(proc.stdout)
    usd = next((c for c in arr if c["code"] == "USD"), None)
    eur = next((c for c in arr if c["code"] == "EUR"), None)
    assert usd and usd["is_base"] is True and usd["exchange_rate"] is None
    assert eur and eur["is_base"] is False and eur["exchange_rate"] is not None


def test_cli_currency_set_base_missing_raises(db_path: Path):
    proc = run_cli(["currency", "set-base", "ZZZ"], db_path, reset=True)
    assert proc.returncode == 2
    assert "[ERROR]" in proc.stderr


def test_cli_currency_duplicate_add_raises(db_path: Path):
    assert run_cli(["currency", "add", "GBP"], db_path, reset=True).returncode == 0
    proc_dup = run_cli(["currency", "add", "GBP"], db_path)
    assert proc_dup.returncode == 2 and "already exists" in proc_dup.stderr
