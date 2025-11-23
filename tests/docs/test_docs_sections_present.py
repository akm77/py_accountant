from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read_text(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_readme_has_core_integration_section() -> None:
    text = read_text("README.md")
    # README должен содержать раздел про интеграцию через core (порты/use cases)
    assert re.search(r"^##\s+Интеграция\s+через\s+core\s*$", text, re.M), (
        "README must contain 'Интеграция через core' section"
    )


def test_integration_guide_has_dual_url_and_core_usage() -> None:
    text = read_text("docs/INTEGRATION_GUIDE.md")
    # Секция про dual URL по-прежнему обязательна
    assert "Runtime vs Migration Database URLs" in text
    # Гайд должен описывать использование через порты и use cases, без упоминания SDK
    assert "application.use_cases_async" in text or "use cases" in text
    assert "application.ports" in text
    assert "py_accountant.sdk" not in text


def test_cheatsheet_exists_and_has_sections() -> None:
    path = ROOT / "docs/ACCOUNTING_CHEATSHEET.md"
    if not path.exists():
        # fallback to correct file name if typo change
        path = ROOT / "docs/ACCOUNTING_CHEATSHEET.md"
    assert path.exists(), "docs/ACCOUNTING_CHEATSHEET.md must exist"
    text = path.read_text(encoding="utf-8")
    assert "Формат строки проводки" in text
    assert "Идемпотентность постинга" in text
