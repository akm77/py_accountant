from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

PACKAGE_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    """Per-test sqlite file path for CLI DB (created on first command)."""
    return tmp_path / "cli_accounts.db"


def run_cli(args: list[str], db_path: Path, reset: bool = False) -> subprocess.CompletedProcess[str]:
    """Run CLI command in a subprocess with DATABASE_URL_ASYNC pointing to db_path."""
    if reset and db_path.exists():
        db_path.unlink()
    env = {"DATABASE_URL_ASYNC": f"sqlite+aiosqlite:///{db_path}"}
    cmd = [sys.executable, "-m", "presentation.cli.main"] + args
    return subprocess.run(cmd, capture_output=True, text=True, cwd=str(PACKAGE_ROOT), env=env)


def test_cli_account_list_empty_returns_empty_json(db_path: Path):
    proc = run_cli(["account", "list", "--json"], db_path, reset=True)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "[]"


def test_cli_account_add_and_list_json(db_path: Path):
    # Need a currency first
    assert run_cli(["currency", "add", "USD"], db_path, reset=True).returncode == 0
    add_proc = run_cli(["account", "add", "Assets:Cash", "USD", "--json"], db_path)
    assert add_proc.returncode == 0, add_proc.stderr
    obj = json.loads(add_proc.stdout)
    assert obj == {"full_name": "Assets:Cash", "currency_code": "USD"}
    list_proc = run_cli(["account", "list", "--json"], db_path)
    assert list_proc.returncode == 0, list_proc.stderr
    data = json.loads(list_proc.stdout)
    assert data == [{"full_name": "Assets:Cash", "currency_code": "USD"}]


def test_cli_account_add_human_output(db_path: Path):
    assert run_cli(["currency", "add", "USD"], db_path, reset=True).returncode == 0
    proc = run_cli(["account", "add", "Income:Sales", "USD"], db_path)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "Account Income:Sales currency=USD"


def test_cli_account_add_invalid_full_name_raises(db_path: Path):
    assert run_cli(["currency", "add", "USD"], db_path, reset=True).returncode == 0
    for bad in ["", " ", ":A", "A:", "A::B", "A: :B"]:
        proc = run_cli(["account", "add", bad, "USD"], db_path)
        assert proc.returncode == 2 and "[ERROR]" in proc.stderr


def test_cli_account_add_invalid_currency_code_raises(db_path: Path):
    assert run_cli(["currency", "add", "USD"], db_path, reset=True).returncode == 0
    for bad in ["", "us", "x" * 11, "usd:usd"]:
        proc = run_cli(["account", "add", "Assets:Cash", bad], db_path)
        assert proc.returncode == 2 and "[ERROR]" in proc.stderr


def test_cli_account_add_missing_currency_raises(db_path: Path):
    # No currencies created
    proc = run_cli(["account", "add", "Assets:Cash", "USD"], db_path, reset=True)
    assert proc.returncode == 2 and "[ERROR]" in proc.stderr


def test_cli_account_duplicate_add_raises(db_path: Path):
    assert run_cli(["currency", "add", "USD"], db_path, reset=True).returncode == 0
    assert run_cli(["account", "add", "Assets:Cash", "USD"], db_path).returncode == 0
    proc_dup = run_cli(["account", "add", "Assets:Cash", "USD"], db_path)
    assert proc_dup.returncode == 2 and "already exists" in proc_dup.stderr


def test_cli_account_list_human_format_multiple(db_path: Path):
    assert run_cli(["currency", "add", "USD"], db_path, reset=True).returncode == 0
    assert run_cli(["account", "add", "Assets:Cash", "USD"], db_path).returncode == 0
    assert run_cli(["account", "add", "Income:Sales", "USD"], db_path).returncode == 0
    proc = run_cli(["account", "list"], db_path)
    assert proc.returncode == 0, proc.stderr
    lines = [text_line for text_line in proc.stdout.splitlines() if text_line.strip()]
    # Expect deterministic lexicographic order by full_name
    assert lines == [
        "Account Assets:Cash currency=USD",
        "Account Income:Sales currency=USD",
    ]


def test_cli_account_get_existing_json(db_path: Path):
    assert run_cli(["currency", "add", "USD"], db_path, reset=True).returncode == 0
    assert run_cli(["account", "add", "Assets:Cash", "USD"], db_path).returncode == 0
    proc = run_cli(["account", "get", "Assets:Cash", "--json"], db_path)
    assert proc.returncode == 0, proc.stderr
    obj = json.loads(proc.stdout)
    assert obj == {"full_name": "Assets:Cash", "currency_code": "USD"}


def test_cli_account_get_missing_raises(db_path: Path):
    proc = run_cli(["account", "get", "Assets:Missing"], db_path, reset=True)
    assert proc.returncode == 2 and "[ERROR]" in proc.stderr


def test_cli_account_add_currency_code_normalized_upper(db_path: Path):
    assert run_cli(["currency", "add", "usd"], db_path, reset=True).returncode == 0
    proc = run_cli(["account", "add", "Assets:Cash", "  usd  ", "--json"], db_path)
    assert proc.returncode == 0
    obj = json.loads(proc.stdout)
    assert obj["currency_code"] == "USD"


def test_cli_account_add_trims_whitespace_full_name(db_path: Path):
    assert run_cli(["currency", "add", "USD"], db_path, reset=True).returncode == 0
    proc = run_cli(["account", "add", "  Assets:Cash  ", "USD", "--json"], db_path)
    assert proc.returncode == 0
    obj = json.loads(proc.stdout)
    assert obj["full_name"] == "Assets:Cash"
