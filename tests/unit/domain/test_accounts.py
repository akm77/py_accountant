import pytest

from py_accountant.domain.accounts import Account
from py_accountant.domain.errors import ValidationError


def test_account_full_name_validation():
    acc = Account(full_name="Assets:Cash:Wallet", currency_code="usd")
    assert acc.name == "Wallet"
    assert acc.segments == ["Assets", "Cash", "Wallet"]
    assert acc.parent_path == "Assets:Cash"
    assert acc.is_root() is False
    assert acc.currency_code == "USD"

    root = Account(full_name="Equity", currency_code="EUR")
    assert root.name == "Equity"
    assert root.parent_path is None
    assert root.is_root() is True


@pytest.mark.parametrize(
    "full_name",
    [
        "",
        " ",
        ":A",
        "A:",
        "A::B",
        "A: :B",
        "A:  :B",
        "A:" + ("B" * 65),
        ("A:" * 100) + "B",
    ],
)
def test_account_full_name_invalid_raises(full_name):
    with pytest.raises(ValidationError):
        Account(full_name=full_name, currency_code="USD")


def test_account_parent_id_optional():
    acc_default = Account(full_name="Assets:Cash", currency_code="USD")
    assert acc_default.parent_id is None
    assert acc_default.name == "Cash"
    assert acc_default.parent_path == "Assets"

    acc_with_parent = Account(full_name="Liabilities:Card", currency_code="usd", parent_id="abc123")
    assert acc_with_parent.parent_id == "abc123"
    assert acc_with_parent.name == "Card"
    assert acc_with_parent.parent_path == "Liabilities"
    assert acc_with_parent.currency_code == "USD"

