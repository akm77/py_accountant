import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]

REQUIRED_DOCS = [
    "docs/FX_AUDIT.md",
    "docs/TRADING_WINDOWS.md",
    "docs/CLI_QUICKSTART.md",
    "docs/PERFORMANCE.md",
    "docs/PARITY_REPORT.md",
    "docs/ARCHITECTURE_OVERVIEW.md",
    "docs/MIGRATION_HISTORY.md",
]

REQUIRED_EXAMPLES = [
    "examples/expected_parity.json",
    "examples/fx_batch.json",
]


def test_docs_files_exist():
    missing = [p for p in REQUIRED_DOCS if not (BASE / p).exists()]
    assert not missing, f"Missing docs: {missing}"


def test_examples_files_exist_and_valid_json():
    for p in REQUIRED_EXAMPLES:
        path = BASE / p
        assert path.exists(), f"Missing example {p}"
        txt = path.read_text(encoding="utf-8").strip()
        assert txt, f"Empty file {p}"
        json.loads(txt)


