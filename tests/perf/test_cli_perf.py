import pytest

from presentation.cli.main import main


@pytest.mark.slow
def test_post_1000_transactions_and_list_ledger():
    # Setup base currency & accounts
    assert main(["currency:add", "USD"]) == 0
    assert main(["currency:set-base", "USD"]) == 0
    assert main(["account:add", "Assets:Cash", "USD"]) == 0
    assert main(["account:add", "Income:Sales", "USD"]) == 0
    for i in range(1000):
        amt = str(1 + (i % 10))
        rc = main(["tx:post", "--line", f"DEBIT:Assets:Cash:{amt}:USD", "--line", f"CREDIT:Income:Sales:{amt}:USD"])
        assert rc == 0
    # Ledger list limited
    assert main(["ledger:list", "Assets:Cash", "--limit", "50"]) == 0



def run(argv):
    return main(argv)


def test_currency_and_account_and_balance_flow():
    assert run(["currency:add", "USD"]) == 0
    assert run(["currency:set-base", "USD"]) == 0
    assert run(["account:add", "Assets:Cash", "USD"]) == 0
    # Post transaction (debit/credit same currency)
    rc = run(["tx:post", "--line", "DEBIT:Assets:Cash:100:USD", "--line", "CREDIT:Assets:Cash:100:USD"])
    assert rc == 0
    # Balance should be 0 (self posting) or reflect net of lines (here zero)
    rc = run(["balance:get", "Assets:Cash"])  # prints
    assert rc == 0


def test_trading_balance_and_json_output():
    # Add base and second currency and rates
    assert run(["currency:add", "USD"]) == 0
    assert run(["currency:set-base", "USD"]) == 0
    assert run(["currency:add", "EUR"]) == 0
    assert run(["fx:update", "EUR", "1.2500"]) == 0
    # Ensure base cash account exists for debit line
    assert run(["account:add", "Assets:Cash", "USD"]) == 0
    # Post cross-currency transaction
    assert run(["account:add", "Income:Sales", "USD"]) == 0
    rc = run(["tx:post", "--line", "DEBIT:Assets:Cash:50:USD", "--line", "CREDIT:Income:Sales:50:USD"])
    assert rc == 0
    # Trading balance detailed requires base
    assert run(["trading:detailed", "--base", "USD", "--json"]) == 0


def test_set_base_without_currency_errors():
    # Attempt to set base to unknown currency -> DomainError exit code 2
    code = run(["currency:set-base", "ABC"])  # ABC not added yet
    assert code == 2


def test_fx_update_invalid_rate():
    assert run(["currency:add", "GBP"]) == 0
    code = run(["fx:update", "GBP", "0"])  # invalid
    assert code == 2
