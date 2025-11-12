from __future__ import annotations

import pytest

from presentation.cli.main import main

pytestmark = pytest.mark.xfail(reason="migrated to async CLI foundation; commands deferred to I22+", strict=False)

def test_fx_audit_events_basic():
    assert main(["currency:add", "USD"]) == 0
    assert main(["currency:set-base", "USD"]) == 0
    assert main(["currency:add", "EUR"]) == 0
    assert main(["fx:update", "EUR", "1.1000"]) == 0
    assert main(["fx:update", "EUR", "1.2000"]) == 0
    rc = main(["diagnostics:rates-audit", "--code", "EUR", "--json"])  # prints events JSON
    assert rc == 0


def test_fx_audit_limit():
    assert main(["currency:add", "USD"]) == 0
    assert main(["currency:set-base", "USD"]) == 0
    assert main(["currency:add", "GBP"]) == 0
    assert main(["fx:update", "GBP", "1.1000"]) == 0
    assert main(["fx:update", "GBP", "1.2000"]) == 0
    assert main(["fx:update", "GBP", "1.3000"]) == 0
    rc = main(["diagnostics:rates-audit", "--code", "GBP", "--limit", "2"])  # human output
    assert rc == 0
