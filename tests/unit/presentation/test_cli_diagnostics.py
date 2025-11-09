from __future__ import annotations

import json

from presentation.cli.main import main


def test_diagnostics_rates_empty_list(tmp_path):
    # No currencies added -> empty list
    rc = main(["diagnostics:rates", "--json"])
    assert rc == 0


def test_diagnostics_rates_with_data(tmp_path):
    # Add currencies and set base, then diagnostics should list them
    assert main(["currency:add", "USD"]) == 0
    assert main(["currency:add", "EUR"]) == 0
    assert main(["currency:set-base", "USD"]) == 0
    assert main(["fx:update", "EUR", "1.5000"]) == 0
    rc = main(["diagnostics:rates", "--json"])
    assert rc == 0

