from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

PACKAGE_ROOT = Path(__file__).resolve().parents[2]


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


@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "idempotency.db"


def test_post_twice_same_key_returns_same_id(db_path: Path):
    prepare_base(db_path)
    key = "KEY-123"
    args = [
        "ledger", "post",
        "--line", "DEBIT:Assets:Cash:100:USD",
        "--line", "CREDIT:Income:Sales:100:USD",
        "--idempotency-key", key,
        "--json",
    ]
    p1 = run_cli(args, db_path)
    assert p1.returncode == 0, p1.stderr
    obj1 = json.loads(p1.stdout)
    p2 = run_cli(args, db_path)
    assert p2.returncode == 0, p2.stderr
    obj2 = json.loads(p2.stdout)
    assert obj1["id"] == obj2["id"]


def test_post_without_key_creates_two_distinct(db_path: Path):
    prepare_base(db_path)
    args = [
        "ledger", "post",
        "--line", "DEBIT:Assets:Cash:100:USD",
        "--line", "CREDIT:Income:Sales:100:USD",
        "--json",
    ]
    p1 = run_cli(args, db_path)
    p2 = run_cli(args, db_path)
    assert p1.returncode == 0 and p2.returncode == 0
    obj1 = json.loads(p1.stdout)
    obj2 = json.loads(p2.stdout)
    assert obj1["id"] != obj2["id"]


def test_cli_meta_vs_flag_priority(db_path: Path):
    prepare_base(db_path)
    args1 = [
        "ledger", "post",
        "--line", "DEBIT:Assets:Cash:50:USD",
        "--line", "CREDIT:Income:Sales:50:USD",
        "--meta", "idempotency_key=foo",
        "--idempotency-key", "bar",
        "--json",
    ]
    p1 = run_cli(args1, db_path)
    assert p1.returncode == 0, p1.stderr
    obj1 = json.loads(p1.stdout)
    # Repeat with same final key (bar)
    p2 = run_cli(args1, db_path)
    assert p2.returncode == 0, p2.stderr
    obj2 = json.loads(p2.stdout)
    assert obj1["id"] == obj2["id"]


def test_same_key_different_payload_first_wins(db_path: Path):
    prepare_base(db_path)
    key = "COLLIDE-1"
    args1 = [
        "ledger", "post",
        "--line", "DEBIT:Assets:Cash:10:USD",
        "--line", "CREDIT:Income:Sales:10:USD",
        "--idempotency-key", key,
        "--json",
    ]
    p1 = run_cli(args1, db_path)
    assert p1.returncode == 0, p1.stderr
    first_id = json.loads(p1.stdout)["id"]
    # Different amount, same key -> should return first id
    args2 = [
        "ledger", "post",
        "--line", "DEBIT:Assets:Cash:11:USD",
        "--line", "CREDIT:Income:Sales:11:USD",
        "--idempotency-key", key,
        "--json",
    ]
    p2 = run_cli(args2, db_path)
    assert p2.returncode == 0, p2.stderr
    second_id = json.loads(p2.stdout)["id"]
    assert first_id == second_id


def test_idempotency_key_missing_is_noop_for_uniqueness(db_path: Path):
    prepare_base(db_path)
    # no key: multiple posts OK
    for _ in range(3):
        p = run_cli([
            "ledger", "post",
            "--line", "DEBIT:Assets:Cash:5:USD",
            "--line", "CREDIT:Income:Sales:5:USD",
            "--json",
        ], db_path)
        assert p.returncode == 0, p.stderr

