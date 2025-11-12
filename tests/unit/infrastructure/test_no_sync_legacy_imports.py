from __future__ import annotations

import importlib
import pathlib
import re
from collections.abc import Iterable  # was typing.Iterable

import pytest

BASE = pathlib.Path(__file__).resolve().parents[2]
REPO_FILE = BASE / "src/infrastructure/persistence/sqlalchemy/repositories.py"
TARGET_MODULE = "infrastructure.persistence.sqlalchemy.repositories"

# Forbidden patterns (excluding Async variants)
FORBIDDEN_PATTERNS: tuple[str, ...] = (
    r"\bSqlAlchemyUnitOfWork\b",
    r"\bSyncUnitOfWorkWrapper\b",
    r"\binfrastructure\.persistence\.sqlalchemy\.repositories\b",
    r"\bSqlAlchemy[A-Za-z]+Repository\b",
)
ALLOWLIST_SUBSTRINGS: tuple[str, ...] = (
    "AsyncSqlAlchemy",
    "repositories_async",
)


def _iter_source_files() -> Iterable[pathlib.Path]:
    for folder in (BASE / "src", BASE / "tests"):
        yield from folder.rglob("*.py")


def _grep_forbidden() -> list[str]:
    offenders: list[str] = []
    compiled = [re.compile(p) for p in FORBIDDEN_PATTERNS]
    for path in _iter_source_files():
        if path == pathlib.Path(__file__):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for i, line in enumerate(text.splitlines(), start=1):
            if any(rx.search(line) for rx in compiled):
                if any(allow in line for allow in ALLOWLIST_SUBSTRINGS):
                    continue
                # ignore reference to target module string inside this test file only
                if path.name == pathlib.Path(__file__).name:
                    continue
                offenders.append(f"{path.relative_to(BASE)}:{i}:{line.strip()}")
    return offenders


def test_repositories_py_file_absent():
    assert not REPO_FILE.exists(), f"repositories.py should be absent, found at {REPO_FILE}"


def test_forbidden_patterns_absent_in_repo():
    offenders = _grep_forbidden()
    assert not offenders, f"Forbidden legacy sync patterns found: {offenders}"


def test_import_of_removed_module_fails():
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(TARGET_MODULE)
