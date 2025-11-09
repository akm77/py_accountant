from __future__ import annotations

from presentation.cli.main import main


def test_diagnostics_rates_human_empty_list():
    # Expect human output of nothing (no error) and exit code 0
    rc = main(["diagnostics:rates"])
    assert rc == 0

