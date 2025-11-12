from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[3]


def run_cli_with_db(db_id: str, args: list[str]) -> subprocess.CompletedProcess[str]:
    db_path = Path(PACKAGE_ROOT) / f"{db_id}.db"
    if not db_path.parent.exists():
        db_path.parent.mkdir(parents=True, exist_ok=True)
    # Remove existing DB to ensure fresh state per test invocation group
    if os.getenv("CLI_DB_RESET", "0") == "1" and db_path.exists():
        db_path.unlink()
    env = os.environ.copy()
    env["DATABASE_URL_ASYNC"] = f"sqlite+aiosqlite:///{db_path}"
    cmd = [sys.executable, "-m", "presentation.cli.main"] + args
    return subprocess.run(cmd, capture_output=True, text=True, cwd=str(PACKAGE_ROOT), env=env)


def run_cli(args: list[str]) -> subprocess.CompletedProcess[str]:
    return run_cli_with_db("cli_currencies_default", args)


def test_cli_currency_list_empty_returns_empty_json():
    # fresh DB
    db_id = "cli_currency_empty"
    list_proc = run_cli_with_db(db_id, ["currency", "list", "--json"])
    assert list_proc.returncode == 0, list_proc.stderr
    assert list_proc.stdout.strip() == "[]"


def test_cli_currency_add_list_json():
    db_id = "cli_currency_add_list"
    os.environ["CLI_DB_RESET"] = "1"
    proc_add = run_cli_with_db(db_id, ["currency", "add", "USD", "--json"])
    os.environ["CLI_DB_RESET"] = "0"
    assert proc_add.returncode == 0, proc_add.stderr
    added = json.loads(proc_add.stdout)
    assert added["code"] == "USD"
    assert added["is_base"] is False
    # List after add
    proc_list = run_cli_with_db(db_id, ["currency", "list", "--json"])
    assert proc_list.returncode == 0, proc_list.stderr
    data = json.loads(proc_list.stdout)
    assert isinstance(data, list) and len(data) == 1
    assert data[0]["code"] == "USD"
    assert data[0]["is_base"] is False
    assert data[0]["exchange_rate"] is None


def test_cli_currency_add_with_rate_and_human_output():
    proc = run_cli(["currency", "add", "EUR", "--rate", "1.2345"])
    assert proc.returncode == 0, proc.stderr
    line = proc.stdout.strip()
    assert line.startswith("Currency EUR base=False rate=")
    # Accept either 1.2345 or quantized 1.234500 (domain uses 6dp)
    assert re.search(r"1\.2345(00)?$", line), line


def test_cli_currency_set_base():
    db_id = "cli_currency_set_base"
    os.environ["CLI_DB_RESET"] = "1"
    assert run_cli_with_db(db_id, ["currency", "add", "USD"]).returncode == 0
    os.environ["CLI_DB_RESET"] = "0"
    assert run_cli_with_db(db_id, ["currency", "add", "EUR", "--rate", "1.2500"]).returncode == 0
    proc = run_cli_with_db(db_id, ["currency", "set-base", "USD", "--json"])
    assert proc.returncode == 0, proc.stderr
    arr = json.loads(proc.stdout)
    usd = next((c for c in arr if c["code"] == "USD"), None)
    assert usd and usd["is_base"] is True and usd["exchange_rate"] is None
    eur = next((c for c in arr if c["code"] == "EUR"), None)
    assert eur and eur["is_base"] is False and eur["exchange_rate"] is not None


def test_cli_currency_set_base_missing_raises():
    proc = run_cli(["currency", "set-base", "ZZZ"])
    assert proc.returncode == 2
    assert "[ERROR]" in proc.stderr


def test_cli_currency_duplicate_add_raises():
    os.environ["CLI_DB_RESET"] = "1"
    assert run_cli(["currency", "add", "GBP"]).returncode == 0
    os.environ["CLI_DB_RESET"] = "0"
    proc_dup = run_cli(["currency", "add", "GBP"])  # duplicate without rate
    assert proc_dup.returncode == 2
    assert "already exists" in proc_dup.stderr
