from presentation.cli.main import main


def test_cli_diagnostics_parity_report_json():
    rc = main(["diagnostics:parity-report", "--json"])  # preset default
    assert rc == 0


def test_cli_diagnostics_rates_history_empty():
    rc = main(["diagnostics:rates-history", "--json"])  # no currencies yet -> empty arrays
    assert rc == 0


def test_cli_diagnostics_rates_history_with_updates():
    assert main(["currency:add", "USD"]) == 0
    assert main(["currency:add", "EUR"]) == 0
    assert main(["currency:set-base", "USD"]) == 0
    assert main(["fx:update", "EUR", "1.2345"]) == 0
    assert main(["fx:update", "EUR", "1.2400"]) == 0
    rc = main(["diagnostics:rates-history", "--json"])  # should include EUR with 2 items
    assert rc == 0

