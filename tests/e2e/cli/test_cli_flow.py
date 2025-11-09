from presentation.cli.main import main


def test_full_cli_flow():
    # Currencies & base
    assert main(["currency:add", "USD"]) == 0
    assert main(["currency:set-base", "USD"]) == 0
    assert main(["currency:add", "EUR"]) == 0
    assert main(["fx:update", "EUR", "1.1000"]) == 0
    # Accounts
    assert main(["account:add", "Assets:Cash", "USD"]) == 0
    assert main(["account:add", "Income:Sales", "USD"]) == 0
    # Post few transactions
    assert main(["tx:post", "--line", "DEBIT:Assets:Cash:100:USD", "--line", "CREDIT:Income:Sales:100:USD"]) == 0
    assert main(["tx:post", "--line", "DEBIT:Assets:Cash:50:USD", "--line", "CREDIT:Income:Sales:50:USD"]) == 0
    # Balance
    assert main(["balance:get", "Assets:Cash", "--json"]) == 0
    # Trading balance (detailed)
    assert main(["trading:detailed", "--base", "USD"]) == 0
    # Ledger list with pagination
    assert main(["ledger:list", "Assets:Cash", "--limit", "10", "--order", "DESC", "--json"]) == 0


