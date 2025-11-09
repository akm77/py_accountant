from __future__ import annotations

import importlib.util
from pathlib import Path


def test_alembic_migration_0002_add_is_base_column():
    root = Path(__file__).resolve().parents[3]
    mig = root / "alembic" / "versions" / "0002_add_is_base_currency.py"
    assert mig.exists(), f"Migration file not found: {mig}"
    spec = importlib.util.spec_from_file_location("migration_0002_add_is_base_currency", mig)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[arg-type]
    assert hasattr(mod, "upgrade")
    assert hasattr(mod, "downgrade")
