from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read_text(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_readme_has_sdk_surface_section() -> None:
    text = read_text("README.md")
    assert re.search(r"^##\s+SDK surface\s*$", text, re.M), "README must contain 'SDK surface' section"
    assert "from py_accountant.sdk" in text


def test_integration_guide_has_dual_url_and_sdk() -> None:
    text = read_text("docs/INTEGRATION_GUIDE.md")
    assert "Runtime vs Migration Database URLs" in text
    assert "Использование как библиотеки (SDK)" in text
    assert "bootstrap.init_app" in text
    assert "post_transaction" in text


def test_cheatsheet_exists_and_has_sections() -> None:
    path = ROOT / "docs/ACCOUNTING_CHEETSHEET.md"
    if not path.exists():
        # fallback to correct file name if typo change
        path = ROOT / "docs/ACCOUNTING_CHEATSHEET.md"
    assert path.exists(), "docs/ACCOUNTING_CHEATSHEET.md must exist"
    text = path.read_text(encoding="utf-8")
    assert "Формат строки проводки" in text
    assert "Идемпотентность постинга" in text

