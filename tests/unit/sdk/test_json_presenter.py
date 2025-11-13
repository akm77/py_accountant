from datetime import UTC, datetime
from decimal import Decimal

from py_accountant.sdk import json as sdk_json


def test_decimal_to_str():
    data = {"x": Decimal("1.20")}
    assert sdk_json.to_dict(data) == {"x": "1.20"}


def test_datetime_aware_to_z():
    dt = datetime(2024, 1, 2, 3, 4, 5, tzinfo=UTC)
    out = sdk_json.to_dict({"t": dt})
    assert out["t"].endswith("Z")
    assert out["t"] == "2024-01-02T03:04:05Z"


def test_datetime_naive_treated_as_utc():
    dt = datetime(2024, 1, 2, 3, 4, 5)  # naive
    out = sdk_json.to_dict({"t": dt})
    assert out["t"].endswith("Z")
    assert out["t"] == "2024-01-02T03:04:05Z"


def test_list_of_dicts_serializes():
    arr = [{"a": 1, "b": Decimal("2.50")}, {"c": None}]
    out = sdk_json.to_dict(arr)
    assert out == [{"a": 1, "b": "2.50"}, {"c": None}]


def test_to_json_deterministic_keys():
    obj = {"b": 1, "a": 2}
    s = sdk_json.to_json(obj)
    assert s == '{"a":2,"b":1}'
