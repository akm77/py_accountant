from __future__ import annotations

from presentation.cli.main import main


def test_unbalanced_transaction_rejected_early():
    assert main(["currency:add", "USD"]) == 0
    assert main(["account:add", "Assets:Cash", "USD"]) == 0
    assert main(["account:add", "Income:Sales", "USD"]) == 0
    rc = main([
        "tx:post",
        "--line", "DEBIT:Assets:Cash:100:USD",
        "--line", "CREDIT:Income:Sales:90:USD",
    ])
    assert rc == 2

