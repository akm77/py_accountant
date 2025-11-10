from __future__ import annotations

import json

from presentation.cli.main import main


def test_parity_report_skipped_without_expected():
    rc = main(["diagnostics:parity-report", "--json"])  # legacy removed -> skipped
    assert rc == 0


def test_parity_report_internal_consistency_with_expected(tmp_path):
    expected = {
        "single_currency_basic": {
            "balances": {"Assets:Cash": "100", "Income:Sales": "100"},
            "base_total": "0"
        }
    }
    exp_file = tmp_path / "expected.json"
    exp_file.write_text(json.dumps(expected), encoding="utf-8")
    rc = main(["diagnostics:parity-report", "--expected-file", str(exp_file), "--json"])
    assert rc == 0

