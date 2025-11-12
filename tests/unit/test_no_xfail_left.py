from __future__ import annotations

from pathlib import Path


def test_no_xfail_markers_left():
    base = Path(__file__).resolve().parents[1]
    self_path = Path(__file__).resolve()
    offenders: list[str] = []
    for path in (base / "..").resolve().glob("tests/**/*.py"):
        if path.resolve() == self_path:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "@pytest.mark.xfail" in text or "pytestmark = pytest.mark.xfail" in text:
            offenders.append(str(path.relative_to(base.parent)))
    assert not offenders, f"xfail markers remain in: {offenders}"
