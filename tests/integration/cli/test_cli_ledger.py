from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

PACKAGE_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "cli_ledger.db"


def run_cli(args: list[str], db_path: Path, reset: bool = False) -> subprocess.CompletedProcess[str]:
    if reset and db_path.exists():
        db_path.unlink()
    env = {"DATABASE_URL_ASYNC": f"sqlite+aiosqlite:///{db_path}"}
    cmd = [sys.executable, "-m", "presentation.cli.main"] + args
    return subprocess.run(cmd, capture_output=True, text=True, cwd=str(PACKAGE_ROOT), env=env)


def prepare_base(db_path: Path) -> None:
    assert run_cli(["currency", "add", "USD"], db_path, reset=True).returncode == 0
    assert run_cli(["currency", "set-base", "USD"], db_path).returncode == 0
    assert run_cli(["account", "add", "Assets:Cash", "USD"], db_path).returncode == 0
    assert run_cli(["account", "add", "Income:Sales", "USD"], db_path).returncode == 0


def test_cli_ledger_post_balanced_usd(db_path: Path):
    prepare_base(db_path)
    proc = run_cli([
        "ledger", "post",
        "--line", "DEBIT:Assets:Cash:10:USD",
        "--line", "CREDIT:Income:Sales:10:USD",
        "--json",
    ], db_path)
    assert proc.returncode == 0, proc.stderr
    obj = json.loads(proc.stdout)
    assert obj.get("id", "").startswith("tx:"), obj
    assert isinstance(obj.get("lines"), list) and len(obj["lines"]) == 2


def test_cli_ledger_post_unbalanced_raises(db_path: Path):
    prepare_base(db_path)
    proc = run_cli([
        "ledger", "post",
        "--line", "DEBIT:Assets:Cash:10:USD",
        "--line", "CREDIT:Income:Sales:9:USD",
    ], db_path)
    assert proc.returncode == 2 and "[ERROR]" in proc.stderr


def test_cli_ledger_post_missing_account_raises(db_path: Path):
    assert run_cli(["currency", "add", "USD"], db_path, reset=True).returncode == 0
    proc = run_cli([
        "ledger", "post",
        "--line", "DEBIT:Assets:Missing:10:USD",
        "--line", "CREDIT:Income:Sales:10:USD",
    ], db_path)
    assert proc.returncode == 2 and "[ERROR]" in proc.stderr


def test_cli_ledger_post_invalid_side_raises(db_path: Path):
    prepare_base(db_path)
    proc = run_cli([
        "ledger", "post",
        "--line", "bad:Assets:Cash:10:USD",
        "--line", "CREDIT:Income:Sales:10:USD",
    ], db_path)
    assert proc.returncode == 2 and "[ERROR]" in proc.stderr


def test_cli_ledger_post_negative_amount_raises(db_path: Path):
    prepare_base(db_path)
    proc = run_cli([
        "ledger", "post",
        "--line", "DEBIT:Assets:Cash:-10:USD",
        "--line", "CREDIT:Income:Sales:-10:USD",
    ], db_path)
    assert proc.returncode == 2 and "[ERROR]" in proc.stderr


def test_cli_ledger_list_json_default_asc(db_path: Path):
    prepare_base(db_path)
    assert run_cli(["ledger", "post", "--line", "DEBIT:Assets:Cash:1:USD", "--line", "CREDIT:Income:Sales:1:USD"], db_path).returncode == 0
    assert run_cli(["ledger", "post", "--line", "DEBIT:Assets:Cash:2:USD", "--line", "CREDIT:Income:Sales:2:USD"], db_path).returncode == 0
    list_proc = run_cli(["ledger", "list", "Assets:Cash", "--json"], db_path)
    assert list_proc.returncode == 0, list_proc.stderr
    data = json.loads(list_proc.stdout)
    assert isinstance(data, list) and len(data) >= 2
    # Expect occurred_at ascending
    times = [item["occurred_at"] for item in data]
    assert times == sorted(times)
    for item in data:
        assert "id" in item and "lines" in item and "occurred_at" in item


def test_cli_ledger_list_invalid_order_raises(db_path: Path):
    prepare_base(db_path)
    proc = run_cli(["ledger", "list", "Assets:Cash", "--order", "WRONG"], db_path)
    assert proc.returncode == 2 and "[ERROR]" in proc.stderr


def test_cli_ledger_list_invalid_account_format_raises(db_path: Path):
    prepare_base(db_path)
    proc = run_cli(["ledger", "list", "Invalid"], db_path)
    assert proc.returncode == 2 and "[ERROR]" in proc.stderr


def test_cli_ledger_list_pagination_limit_zero_empty(db_path: Path):
    prepare_base(db_path)
    assert run_cli(["ledger", "post", "--line", "DEBIT:Assets:Cash:1:USD", "--line", "CREDIT:Income:Sales:1:USD"], db_path).returncode == 0
    proc = run_cli(["ledger", "list", "Assets:Cash", "--limit", "0", "--json"], db_path)
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert data == []


def test_cli_ledger_balance_self_post_zero(db_path: Path):
    prepare_base(db_path)
    # Post debit and credit to the same account to simulate zero balance (domain balance use case aggregates)
    assert run_cli(["ledger", "post", "--line", "DEBIT:Assets:Cash:5:USD", "--line", "CREDIT:Assets:Cash:5:USD"], db_path).returncode == 0
    proc_h = run_cli(["ledger", "balance", "Assets:Cash"], db_path)
    assert proc_h.returncode == 0 and proc_h.stdout.strip().startswith("Balance Assets:Cash = ")
    proc_j = run_cli(["ledger", "balance", "Assets:Cash", "--json"], db_path)
    assert proc_j.returncode == 0
    obj = json.loads(proc_j.stdout)
    assert obj["account_full_name"] == "Assets:Cash"
    assert obj["balance"].endswith("0.00")


def test_cli_ledger_window_invalid_dates_raises(db_path: Path):
    prepare_base(db_path)
    proc = run_cli(["ledger", "list", "Assets:Cash", "--start", "2025-01-02T00:00:00", "--end", "2025-01-01T00:00:00"], db_path)
    assert proc.returncode == 2 and "[ERROR]" in proc.stderr

# Optional tests

def test_cli_ledger_post_with_memo_and_meta(db_path: Path):
    prepare_base(db_path)
    proc = run_cli([
        "ledger", "post",
        "--line", "DEBIT:Assets:Cash:10:USD",
        "--line", "CREDIT:Income:Sales:10:USD",
        "--memo", "Sale #123",
        "--meta", "channel=web",
        "--meta", "country=US",
        "--json",
    ], db_path)
    assert proc.returncode == 0
    obj = json.loads(proc.stdout)
    assert obj["memo"] == "Sale #123"
    assert obj["meta"] == {"channel": "web", "country": "US"}


def test_cli_ledger_balance_as_of_parsed_utc(db_path: Path):
    prepare_base(db_path)
    # Should accept naive and return success
    proc = run_cli(["ledger", "balance", "Assets:Cash", "--as-of", "2025-01-01T00:00:00"], db_path)
    assert proc.returncode == 0

