from __future__ import annotations

import pytest

from presentation.cli.main import main

pytestmark = pytest.mark.xfail(reason="migrated to async CLI foundation; commands deferred to I22+", strict=False)

def test_diagnostics_rates_human_empty_list():
    # Expect human output of nothing (no error) and exit code 0
    rc = main(["diagnostics:rates"])
    assert rc == 0
