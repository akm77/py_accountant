from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

PACKAGE_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "cli_ledger_files.db"


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


def test_post_from_csv_minimal_ok(tmp_path: Path, db_path: Path):
    prepare_base(db_path)
    prepare_eur(db_path)
    csv_path = tmp_path / "tx.csv"
    csv_path.write_text("side,account,amount,currency\nDEBIT,Assets:Broker,100,EUR\nCREDIT,Assets:Cash,112,USD\n", encoding="utf-8")

    proc = run_cli([
        "ledger", "post",
        "--lines-file", str(csv_path),
        "--json",
    ], db_path)
    assert proc.returncode == 0, proc.stderr
    obj = json.loads(proc.stdout)
    assert len(obj.get("lines", [])) == 2


def test_post_from_json_objects_ok(tmp_path: Path, db_path: Path):
    prepare_base(db_path)
    prepare_eur(db_path)
    json_path = tmp_path / "tx.json"
    payload = [
        {"side": "DEBIT", "account": "Assets:Broker", "amount": "100", "currency": "EUR"},
        {"side": "CREDIT", "account": "Assets:Cash", "amount": "112", "currency": "USD"},
    ]
    json_path.write_text(json.dumps(payload), encoding="utf-8")

    proc = run_cli([
        "ledger", "post",
        "--lines-file", str(json_path),
        "--json",
    ], db_path)
    assert proc.returncode == 0, proc.stderr
    obj = json.loads(proc.stdout)
    assert len(obj.get("lines", [])) == 2


def test_post_from_json_lines_ok(tmp_path: Path, db_path: Path):
    prepare_base(db_path)
    prepare_eur(db_path)
    json_path = tmp_path / "tx_lines.json"
    payload = [
        "DEBIT:Assets:Broker:100:EUR",
        "CREDIT:Assets:Cash:112:USD",
    ]
    json_path.write_text(json.dumps(payload), encoding="utf-8")

    proc = run_cli([
        "ledger", "post",
        "--lines-file", str(json_path),
        "--json",
    ], db_path)
    assert proc.returncode == 0, proc.stderr
    obj = json.loads(proc.stdout)
    assert len(obj.get("lines", [])) == 2


def test_post_from_file_and_cli_lines_merged_ok(tmp_path: Path, db_path: Path):
    prepare_base(db_path)
    prepare_eur(db_path)
    csv_path = tmp_path / "merge.csv"
    csv_path.write_text("side,account,amount,currency\nCREDIT,Income:Sales,12,USD\n", encoding="utf-8")

    proc = run_cli([
        "ledger", "post",
        "--line", "DEBIT:Assets:Cash:12:USD",
        "--lines-file", str(csv_path),
        "--json",
    ], db_path)
    assert proc.returncode == 0, proc.stderr
    obj = json.loads(proc.stdout)
    # Ensure order preserved: first CLI line then file line
    assert obj["lines"][0]["side"] == "DEBIT"
    assert obj["lines"][1]["side"] == "CREDIT"


def test_csv_missing_required_field_raises(tmp_path: Path, db_path: Path):
    prepare_base(db_path)
    bad_csv = tmp_path / "bad.csv"
    # Missing currency header
    bad_csv.write_text("side,account,amount\nDEBIT,Assets:Cash,10\n", encoding="utf-8")

    proc = run_cli([
        "ledger", "post",
        "--lines-file", str(bad_csv),
    ], db_path)
    assert proc.returncode == 2
    assert "missing" in proc.stderr.lower()
    assert "currency" in proc.stderr.lower()


def test_json_malformed_raises(tmp_path: Path, db_path: Path):
    prepare_base(db_path)
    bad_json = tmp_path / "bad.json"
    bad_json.write_text("[\n  { \"side\": \"DEBIT\", \"account\": \"Assets:Cash\", \"amount\": \"10\", \"currency\": \"USD\" },\n  oops\n]", encoding="utf-8")

    proc = run_cli([
        "ledger", "post",
        "--lines-file", str(bad_json),
    ], db_path)
    assert proc.returncode == 2
    assert "invalid json" in proc.stderr.lower()


def test_file_not_found_raises(db_path: Path):
    prepare_base(db_path)
    proc = run_cli([
        "ledger", "post",
        "--lines-file", "./no_such_file.csv",
    ], db_path)
    assert proc.returncode == 2
    assert "not found" in proc.stderr.lower()


def test_empty_file_raises(tmp_path: Path, db_path: Path):
    prepare_base(db_path)
    empty_csv = tmp_path / "empty.csv"
    empty_csv.write_text("", encoding="utf-8")

    proc = run_cli([
        "ledger", "post",
        "--lines-file", str(empty_csv),
    ], db_path)
    assert proc.returncode == 2
    assert "no lines" in proc.stderr.lower()

