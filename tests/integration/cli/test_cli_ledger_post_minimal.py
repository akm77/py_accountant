from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

PACKAGE_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "cli_ledger_minimal.db"


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


def prepare_eur(db_path: Path) -> None:
    assert run_cli(["currency", "add", "EUR", "--rate", "1.120000"], db_path).returncode == 0
    assert run_cli(["account", "add", "Assets:Broker", "EUR"], db_path).returncode == 0


def test_post_with_rate_and_occurred_at_json_success(db_path: Path):
    prepare_base(db_path)
    proc = run_cli([
        "ledger", "post",
        "--line", "DEBIT:Assets:Cash:100:USD",
        "--line", "CREDIT:Income:Sales:100:USD",
        "--occurred-at", "2025-01-02T03:04:05Z",
        "--json",
    ], db_path)
    assert proc.returncode == 0, proc.stderr
    obj = json.loads(proc.stdout)
    assert obj.get("occurred_at") == "2025-01-02T03:04:05+00:00" or obj.get("occurred_at") == "2025-01-02T03:04:05Z"
    assert len(obj.get("lines", [])) == 2


def test_post_with_optional_rate_success(db_path: Path):
    prepare_base(db_path)
    prepare_eur(db_path)
    # Add EUR rate relative to USD via line rate
    proc = run_cli([
        "ledger", "post",
        "--line", "DEBIT:Assets:Broker:100:EUR:1.120000",
        "--line", "CREDIT:Assets:Cash:112:USD",
        "--json",
    ], db_path)
    assert proc.returncode == 0, proc.stderr
    obj = json.loads(proc.stdout)
    assert len(obj.get("lines", [])) == 2


def test_invalid_line_format_exit2(db_path: Path):
    prepare_base(db_path)
    proc = run_cli([
        "ledger", "post",
        "--line", "DEBIT::100:USD",
        "--line", "CREDIT:Income:Sales:100:USD",
    ], db_path)
    assert proc.returncode == 2
    assert "Expected 'SIDE:Account:Amount:Currency[:Rate]'" in proc.stderr


def test_non_positive_amount_exit2(db_path: Path):
    prepare_base(db_path)
    proc = run_cli([
        "ledger", "post",
        "--line", "DEBIT:Assets:Cash:0:USD",
        "--line", "CREDIT:Income:Sales:0:USD",
    ], db_path)
    assert proc.returncode == 2
    assert "Amount must be > 0" in proc.stderr


def test_unknown_currency_exit2(db_path: Path):
    # Prepare USD only, no XYZ
    assert run_cli(["currency", "add", "USD"], db_path, reset=True).returncode == 0
    assert run_cli(["currency", "set-base", "USD"], db_path).returncode == 0
    assert run_cli(["account", "add", "Assets:Cash", "USD"], db_path).returncode == 0
    proc = run_cli([
        "ledger", "post",
        "--line", "DEBIT:Assets:Cash:10:XYZ",
        "--line", "CREDIT:Income:Sales:10:USD",
    ], db_path)
    assert proc.returncode == 2


def test_unbalanced_ledger_exit2(db_path: Path):
    prepare_base(db_path)
    proc = run_cli([
        "ledger", "post",
        "--line", "DEBIT:Assets:Cash:10:USD",
        "--line", "CREDIT:Income:Sales:9:USD",
    ], db_path)
    assert proc.returncode == 2
    assert "balanced" in proc.stderr.lower() or "unbalance" in proc.stderr.lower()
