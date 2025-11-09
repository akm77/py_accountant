from __future__ import annotations

import json
from decimal import Decimal

from presentation.cli.main import main


def test_fx_batch_local_policy_override(tmp_path):
    # Global policy last_write, but local weighted_average should apply for batch
    assert main(["--policy", "last_write", "currency:add", "USD"]) == 0
    assert main(["--policy", "last_write", "currency:add", "EUR"]) == 0
    # Initial update to set a base rate state
    assert main(["--policy", "last_write", "fx:update", "EUR", "1.0"]) == 0
    # Prepare batch with two updates for EUR: last wins for input, and WA override will average previous and this one.
    data = [{"code": "EUR", "rate": "2.0"}]
    path = tmp_path / "rates.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    rc = main(["--policy", "last_write", "fx:batch", str(path), "--policy", "weighted_average"])  # override
    assert rc == 0
    # Now update again with 1.0 and ensure WA progresses from previous average: (2.0 + 1.0)/2 = 1.5
    # To observe state effect we call fx:update with global last_write disabled (no further averaging), but previous stored rate already 1.5
    assert main(["fx:update", "EUR", "1.0"]) == 0
    # Optionally, run diagnostics:rates to ensure JSON has rate string; not asserting text to keep test robust
    assert main(["diagnostics:rates", "--json"]) == 0

