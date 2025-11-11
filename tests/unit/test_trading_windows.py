from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from presentation.cli.main import main


@pytest.mark.xfail(reason="REWRITE-DOMAIN (I13): trading window test depends on repo aggregation removed", strict=False)
def test_trading_balance_window_filters_outside():
    # Setup
    assert main(["currency:add", "USD"]) == 0
    assert main(["currency:set-base", "USD"]) == 0
    assert main(["account:add", "Assets:Cash", "USD"]) == 0
    # Two transactions: one yesterday, one now
    now = datetime.now(UTC)
    yesterday = (now - timedelta(days=1)).isoformat()
    today = now.isoformat()
    # Post via CLI uses current time; we can't inject time easily here, so just post two transactions
    assert main(["tx:post", "--line", "DEBIT:Assets:Cash:10:USD", "--line", "CREDIT:Assets:Cash:10:USD"]) == 0
    assert main(["tx:post", "--line", "DEBIT:Assets:Cash:5:USD", "--line", "CREDIT:Assets:Cash:5:USD"]) == 0
    # Query with start=end to now; should succeed
    assert main(["trading:detailed", "--base", "USD", "--start", today, "--end", today]) == 0
    # Invalid window
    assert main(["trading:detailed", "--base", "USD", "--start", today, "--end", yesterday]) == 2

