from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

PACKAGE_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "cli_trading.db"


def run_cli(args: list[str], db_path: Path, reset: bool = False) -> subprocess.CompletedProcess[str]:
    if reset and db_path.exists():
        db_path.unlink()
    env = {"DATABASE_URL_ASYNC": f"sqlite+aiosqlite:///{db_path}"}
    cmd = [sys.executable, "-m", "presentation.cli.main"] + args
    return subprocess.run(cmd, capture_output=True, text=True, cwd=str(PACKAGE_ROOT), env=env)


def prepare_base_usd(db_path: Path) -> None:
    assert run_cli(["currency", "add", "USD"], db_path, reset=True).returncode == 0
    assert run_cli(["currency", "set-base", "USD"], db_path).returncode == 0
    assert run_cli(["account", "add", "Assets:Cash", "USD"], db_path).returncode == 0
    assert run_cli(["account", "add", "Income:Sales", "USD"], db_path).returncode == 0


def prepare_eur(db_path: Path, rate: str = "1.100000") -> None:
    assert run_cli(["currency", "add", "EUR", "--rate", rate], db_path).returncode == 0


# --- Mandatory tests ---

def test_cli_trading_raw_empty_returns_empty_json(db_path: Path):
    # Empty DB should return [] for raw --json
    proc = run_cli(["trading", "raw", "--json"], db_path, reset=True)
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert data == []


def test_cli_trading_raw_usd_simple(db_path: Path):
    prepare_base_usd(db_path)
    # Post 2 USD transactions: 10 debit/credit and 8 debit/credit
    assert run_cli([
        "ledger", "post",
        "--line", "DEBIT:Assets:Cash:10:USD",
        "--line", "CREDIT:Income:Sales:10:USD",
    ], db_path).returncode == 0
    assert run_cli([
        "ledger", "post",
        "--line", "DEBIT:Assets:Cash:8:USD",
        "--line", "CREDIT:Income:Sales:8:USD",
    ], db_path).returncode == 0
    proc = run_cli(["trading", "raw", "--json"], db_path)
    assert proc.returncode == 0, proc.stderr
    items = json.loads(proc.stdout)
    assert isinstance(items, list) and len(items) == 1
    line = items[0]
    assert line["currency_code"] == "USD"
    assert line["debit"].endswith(".00") and line["credit"].endswith(".00")
    assert line["net"].endswith(".00")


def test_cli_trading_detailed_eur_converted_to_usd(db_path: Path):
    prepare_base_usd(db_path)
    prepare_eur(db_path, rate="1.100000")
    # Post EUR transaction
    assert run_cli([
        "ledger", "post",
        "--line", "DEBIT:Assets:Cash:110:EUR",
        "--line", "CREDIT:Income:Sales:110:EUR",
    ], db_path).returncode == 0
    proc = run_cli(["trading", "detailed", "--json"], db_path)
    assert proc.returncode == 0, proc.stderr
    items = json.loads(proc.stdout)
    # Expect one EUR line with base USD, used_rate "1.100000"
    eur = [i for i in items if i["currency_code"] == "EUR"][0]
    assert eur["base_currency_code"] == "USD"
    assert eur["used_rate"] == "1.100000"
    # base amounts should be quantized to 2 decimals
    assert eur["debit_base"].endswith(".00")
    assert eur["credit_base"].endswith(".00")
    assert eur["net_base"].endswith(".00")


def test_cli_trading_window_invalid_dates_raises(db_path: Path):
    prepare_base_usd(db_path)
    proc = run_cli(["trading", "raw", "--start", "2025-01-02T00:00:00", "--end", "2025-01-01T00:00:00"], db_path)
    assert proc.returncode == 2 and "[ERROR]" in proc.stderr


def test_cli_trading_invalid_meta_item_raises(db_path: Path):
    prepare_base_usd(db_path)
    proc = run_cli(["trading", "raw", "--meta", "invalid_meta"], db_path)
    assert proc.returncode == 2 and "[ERROR]" in proc.stderr


def test_cli_trading_detailed_missing_base_raises(db_path: Path):
    # Add EUR only, no base set, and don't pass --base -> error
    assert run_cli(["currency", "add", "EUR", "--rate", "1.000000"], db_path, reset=True).returncode == 0
    # Ledger post optional to ensure no lines present shouldn't hide base validation
    proc = run_cli(["trading", "detailed", "--json"], db_path)
    assert proc.returncode == 2 and "[ERROR]" in proc.stderr


# --- Optional tests ---

def test_cli_trading_raw_with_meta_filter(db_path: Path):
    prepare_base_usd(db_path)
    # Post two transactions with different meta; currently ledger post CLI supports --meta
    assert run_cli([
        "ledger", "post",
        "--line", "DEBIT:Assets:Cash:5:USD",
        "--line", "CREDIT:Income:Sales:5:USD",
        "--meta", "channel=web",
    ], db_path).returncode == 0
    assert run_cli([
        "ledger", "post",
        "--line", "DEBIT:Assets:Cash:7:USD",
        "--line", "CREDIT:Income:Sales:7:USD",
        "--meta", "channel=store",
    ], db_path).returncode == 0
    proc = run_cli(["trading", "raw", "--meta", "channel=web", "--json"], db_path)
    assert proc.returncode == 0
    items = json.loads(proc.stdout)
    assert isinstance(items, list) and len(items) == 1
    assert items[0]["currency_code"] == "USD"


def test_cli_trading_detailed_with_explicit_base_ok(db_path: Path):
    prepare_base_usd(db_path)
    prepare_eur(db_path, rate="1.250000")
    # explicit base should still work
    proc = run_cli(["trading", "detailed", "--base", "usd", "--json"], db_path)
    assert proc.returncode == 0

