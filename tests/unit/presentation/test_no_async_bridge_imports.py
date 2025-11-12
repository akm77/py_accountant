from __future__ import annotations

import importlib
import pathlib


def test_async_bridge_module_absent():
    """Importing presentation.async_bridge must fail after I27 removal."""
    try:
        importlib.import_module("presentation.async_bridge")
    except ModuleNotFoundError:
        pass
    else:
        raise AssertionError("presentation.async_bridge unexpectedly importable")


def test_no_source_references_to_async_bridge():
    """There should be no string refs to 'presentation.async_bridge' in src/ and tests/."""
    root = pathlib.Path(__file__).resolve().parents[2]
    hits = []
    for folder in (root / "src", root / "tests"):
        if not folder.exists():
            continue
        for path in folder.rglob("*.py"):
            text = path.read_text(encoding="utf-8", errors="ignore")
            if "presentation.async_bridge" in text:
                hits.append(str(path))
    assert not hits, f"Found stale async_bridge imports in: {hits}"

