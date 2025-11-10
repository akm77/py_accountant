import json
from decimal import Decimal
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
EXPECTED = BASE / "examples/expected_parity.json"


def test_expected_parity_json_structure():
    assert EXPECTED.exists(), "expected_parity.json missing"
    data = json.loads(EXPECTED.read_text(encoding="utf-8"))
    assert isinstance(data, dict), "Top level must be object"
    for scenario, payload in data.items():
        assert isinstance(payload, dict), f"Scenario {scenario} must map to object"
        assert "balances" in payload, f"Scenario {scenario} missing balances"
        assert "base_total" in payload, f"Scenario {scenario} missing base_total"
        balances = payload["balances"]
        assert isinstance(balances, dict), "balances must be object"
        for acc, amt in balances.items():
            # Validate Decimal convertibility
            Decimal(str(amt))
        Decimal(str(payload["base_total"]))


