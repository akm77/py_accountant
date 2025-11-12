from __future__ import annotations

import importlib
import inspect
import pathlib
import re
import warnings

import pytest

BASE = pathlib.Path(__file__).resolve().parents[2]
TARGET_MODULE = "infrastructure.persistence.sqlalchemy.repositories"
STUB_NAMES = [
    "SqlAlchemyCurrencyRepository",
    "SqlAlchemyAccountRepository",
    "SqlAlchemyTransactionRepository",
    "SqlAlchemyBalanceRepository",
    "SqlAlchemyExchangeRateEventsRepository",
]
MESSAGE_SUBSTRINGS = ["DEPRECATED", "repositories_async.py"]


def _grep(pattern: str) -> list[str]:
    """Return list of lines 'path:lineno:text' matching regex pattern in src/ and tests/ excluding this test file."""
    results: list[str] = []
    rx = re.compile(pattern)
    for folder in (BASE / "src", BASE / "tests"):
        for path in folder.rglob("*.py"):
            if path.name == pathlib.Path(__file__).name:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for i, line in enumerate(text.splitlines(), start=1):
                if rx.search(line):
                    # allow async repositories_async imports
                    if "repositories_async" in line:
                        continue
                    # exclude references to test module itself if any
                    if TARGET_MODULE in line:
                        continue
                    results.append(f"{path.relative_to(BASE)}:{i}:{line.strip()}")
    return results


def test_sync_repositories_not_imported_elsewhere():
    offenders = _grep(r"repositories\.py|SqlAlchemy[A-Za-z]+Repository")
    assert not offenders, f"Found legacy sync repository usage: {offenders}"  # hard fail


def test_sync_repositories_deprecated_import_and_classes_raise():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        mod = importlib.import_module(TARGET_MODULE)
        assert hasattr(mod, "MESSAGE")
        for name in STUB_NAMES:
            cls = getattr(mod, name)
            assert inspect.isclass(cls)
            with pytest.raises(RuntimeError) as ei:
                cls()  # instantiation should fail
            msg = str(ei.value)
            for sub in MESSAGE_SUBSTRINGS:
                assert sub in msg
        # At least one deprecation warning should be emitted
        dep_warnings = [w for w in caught if issubclass(w.category, DeprecationWarning)]
        assert dep_warnings, "No DeprecationWarning captured on instantiation"
        for w in dep_warnings:
            text = str(w.message)
            for sub in MESSAGE_SUBSTRINGS:
                assert sub in text


def test_module_public_surface_matches_stub_names():
    mod = importlib.import_module(TARGET_MODULE)
    exported = getattr(mod, "__all__", [])
    assert sorted(exported) == sorted(STUB_NAMES)

