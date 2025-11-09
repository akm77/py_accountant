import pytest

pytest.skip("py_fledger.Book legacy tests skipped (deprecated). Use parity tests instead.", allow_module_level=True)

from py_fledger import book

# Use in-memory SQLite for tests to avoid external Postgres dependency
TEST_DB = "sqlite+pysqlite:///:memory:"


@pytest.fixture(scope="module")
def bk():
    b = book(TEST_DB)
    b.init()
    yield b


def test_create_currencies(bk):
    bk.create_currency("USD")
    bk.create_currency("RUB")


def test_throw_on_account_create_with_non_existing_parent(bk):
    with pytest.raises(Exception):
        bk.create_account("Assets:usdt")


def test_throw_on_wrong_account_name(bk):
    with pytest.raises(Exception):
        bk.create_account("Assets$:usdt")


def test_create_accounts(bk):
    bk.create_account("Assets")
    bk.create_account("Assets:usdt")
    bk.create_account("Assets:bank")
    bk.create_account("Assets:bank:AlfaBank", "RUB")
    bk.create_account("Assets:bank:Huntington")
    bk.create_account("UserBalances")
    bk.create_account("UserBalances:1")


def test_transactions_user1_top_up(bk):
    e = bk.entry("User 1 top up")
    e.debit("Assets:usdt", 10000, {"type": "userTopUp"})
    e.credit("UserBalances:1", 10000, {"type": "userTopUp"})
    e.commit()


def test_throw_on_create_tx_for_non_existing_account(bk):
    e = bk.entry("User 2 top up")
    e.debit("Assets:usdt", 10000, {"type": "userTopUp"})
    e.credit("UserBalances:2", 10000, {"type": "userTopUp"})
    with pytest.raises(Exception):
        e.commit()


def test_partial_transfer_usdt_to_huntington(bk):
    bk.entry("Transfer").credit("Assets:usdt", 9500).debit("Assets:bank:Huntington", 9500).commit()


def test_user1_rub_top_up(bk):
    bk.entry("User 1 RUB top up").debit("Assets:bank:AlfaBank", 600300, {"type": "userTopUp"}, 60.03).credit(
        "UserBalances:1", 10000, {"type": "userTopUp"}
    ).commit()


def test_balances(bk):
    assert bk.balance("Assets:usdt") == "500"
    assert bk.balance("UserBalances:1") == "-20000"
    assert bk.balance("Assets:bank") == "19500"


def test_history(bk):
    txs = bk.ledger("Assets")
    assert len(txs) == 4
    assert txs[0].id == txs[0].id  # ids exist
    txs2 = bk.ledger("Assets", None, {"order": "asc"})
    assert txs2[0].id < txs2[-1].id
    p = bk.ledger("Assets", None, {"limit": 1})
    assert len(p) == 1
    t3 = bk.ledger("Assets", {"type": "userTopUp"})
    assert len(t3) == 2


def test_helpers(bk):
    all_acc = bk.get_accounts()
    assert any(a.full_name == "Assets" for a in all_acc)
    assets_sub = bk.get_accounts("Assets")
    assert len(assets_sub) >= 2


def test_multi_currency(bk):
    bk.entry("User 1 RUB top up").debit("Assets:bank:AlfaBank", 700000, {"type": "userTopUp"}, 70).credit(
        "UserBalances:1", 10000, {"type": "userTopUp"}
    ).commit()
    tb = bk.trading_balance()
    assert tb["currency"]["RUB"] == "1300300"
    assert tb["currency"]["USD"] == "-20000"

    bk.entry("exchange RUB to USD").credit("Assets:bank:AlfaBank", 1300300, None, 100).debit(
        "Assets:bank:Huntington", 13003
    ).commit()
    tb2 = bk.trading_balance()
    assert tb2["currency"]["RUB"] == "0"
    assert tb2["currency"]["USD"] == "-6997"
    assert tb2["base"] == "-6997"
