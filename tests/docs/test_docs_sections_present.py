from pathlib import Path

BASE = Path(__file__).resolve().parents[2]

REQUIRED_SECTIONS = {
    "docs/MIGRATION_HISTORY.md": ["Async vs Sync URL"],
    "docs/INTEGRATION_GUIDE.md": ["Runtime vs Migration Database URLs"],
    "README.md": ["ENV переменные"],
}


def test_required_doc_sections_present():
    missing = []
    for rel, headers in REQUIRED_SECTIONS.items():
        text = (BASE / rel).read_text(encoding="utf-8")
        for h in headers:
            if h not in text:
                missing.append(f"{rel}:{h}")
    assert not missing, f"Missing doc headers: {missing}"

