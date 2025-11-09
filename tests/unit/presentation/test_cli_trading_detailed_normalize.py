from __future__ import annotations

from presentation.cli.main import main


def test_trading_detailed_normalize_multi_currency():
    # Setup two currencies
    assert main(["currency:add", "USD"]) == 0
    assert main(["currency:add", "EUR"]) == 0
    assert main(["currency:set-base", "USD"]) == 0
    # Post accounts
    assert main(["account:add", "Assets:Cash", "USD"]) == 0
    assert main(["account:add", "Income:Sales", "EUR"]) == 0
    # Balanced multi-currency transaction: 100 USD == 123.45 EUR / 1.2345
    assert main([
        "tx:post",
        "--line", "DEBIT:Assets:Cash:100:USD",
        "--line", "CREDIT:Income:Sales:123.45:EUR:1.2345",
    ]) == 0
    # Detailed trading balance without normalization
    assert main(["trading:detailed", "--base", "USD", "--json"]) == 0
    # Detailed trading balance with normalization (should also succeed)
    assert main(["trading:detailed", "--base", "USD", "--normalize", "--json"]) == 0
