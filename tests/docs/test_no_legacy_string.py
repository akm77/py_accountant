from pathlib import Path

BASE = Path(__file__).resolve().parents[2]

EXCEPTIONS = {"docs/MIGRATION_HISTORY.md"}
LEGACY = "py_" + "fledger"


def test_no_legacy_string_outside_migration_history():
    occurrences = []
    for p in BASE.rglob("*.py"):
        txt = p.read_text(encoding="utf-8", errors="ignore")
        if LEGACY in txt:
            # ignore this very file
            if p.name == Path(__file__).name:
                continue
            occurrences.append(str(p))
    assert not occurrences, f"Unexpected legacy references: {occurrences}"
    for p in BASE.rglob("*.md"):
        rel = p.relative_to(BASE).as_posix()
        if rel in EXCEPTIONS:
            continue
        txt = p.read_text(encoding="utf-8", errors="ignore")
        assert LEGACY not in txt, f"Legacy mention in {rel}"
