from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine, inspect

from alembic import command


def test_alembic_upgrade_creates_tables(tmp_path):
    db_url = f"sqlite+pysqlite:///{tmp_path}/alembic.db"
    ini_path = Path("alembic.ini").resolve()
    cfg = Config(str(ini_path))
    cfg.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(cfg, "head")
    engine = create_engine(db_url, future=True)
    insp = inspect(engine)
    tables = set(insp.get_table_names())
    expected = {"currencies", "accounts", "journals", "transaction_lines", "balances"}
    for t in expected:
        assert t in tables


def test_alembic_downgrade_removes_tables(tmp_path):
    db_url = f"sqlite+pysqlite:///{tmp_path}/alembic_down.db"
    ini_path = Path("alembic.ini").resolve()
    cfg = Config(str(ini_path))
    cfg.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")
    engine = create_engine(db_url, future=True)
    insp = inspect(engine)
    remaining = set(insp.get_table_names())
    # Only Alembic's version table may remain
    assert remaining <= {"alembic_version"}
