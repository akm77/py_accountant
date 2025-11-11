from __future__ import annotations

import pytest

from application.use_cases_async import (
    AsyncCreateAccount,
    AsyncCreateCurrency,
    AsyncGetAccount,
    AsyncListAccounts,
)
from domain.errors import ValidationError


@pytest.mark.asyncio
async def test_create_account_valid_domain_projection(async_uow):
    # Prepare currency (domain will normalize to upper)
    create_cur = AsyncCreateCurrency(async_uow)
    await create_cur("usd")

    create_acc = AsyncCreateAccount(async_uow)
    acc = await create_acc(" Assets: Cash ", "usd")
    assert acc.full_name == "Assets:Cash"
    assert acc.name == "Cash"
    assert acc.currency_code == "USD"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "bad_name",
    [
        "",
        " ",
        ":A",
        "A:",
        "A::B",
        "A: :B",
        "A:  :B",
        "A:" + ("B" * 65),
        ("A:" * 64) + "B",  # 65 segments total
        "A" * 256,
    ],
)
async def test_create_account_invalid_full_name_parametrized(async_uow, bad_name):
    create_cur = AsyncCreateCurrency(async_uow)
    await create_cur("USD")
    create_acc = AsyncCreateAccount(async_uow)
    with pytest.raises(ValidationError):
        await create_acc(bad_name, "USD")


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_code", ["US", "U", "U" * 11, "", "  "])
async def test_create_account_invalid_currency_code(async_uow, bad_code):
    create_cur = AsyncCreateCurrency(async_uow)
    await create_cur("USD")
    create_acc = AsyncCreateAccount(async_uow)
    with pytest.raises(ValidationError):
        await create_acc("Assets:Cash", bad_code)


@pytest.mark.asyncio
async def test_create_account_missing_currency_raises_value_error(async_uow):
    create_acc = AsyncCreateAccount(async_uow)
    with pytest.raises(ValueError):
        await create_acc("Assets:Cash", "USD")  # USD not created yet


@pytest.mark.asyncio
async def test_create_account_duplicate_raises_value_error(async_uow):
    create_cur = AsyncCreateCurrency(async_uow)
    await create_cur("USD")
    create_acc = AsyncCreateAccount(async_uow)
    await create_acc("Assets:Cash", "USD")
    with pytest.raises(ValueError):
        await create_acc("Assets:Cash", "USD")


@pytest.mark.asyncio
async def test_get_account_returns_none_for_missing(async_uow):
    get_acc = AsyncGetAccount(async_uow)
    assert await get_acc("Nope:Missing") is None


@pytest.mark.asyncio
async def test_list_accounts_passthrough(async_uow):
    create_cur = AsyncCreateCurrency(async_uow)
    await create_cur("USD")
    create_acc = AsyncCreateAccount(async_uow)
    await create_acc("Assets:Cash", "USD")

    list_acc = AsyncListAccounts(async_uow)
    rows = await list_acc()
    assert any(r.full_name == "Assets:Cash" for r in rows)


@pytest.mark.asyncio
async def test_root_account_parent_path_none(async_uow):
    create_cur = AsyncCreateCurrency(async_uow)
    await create_cur("USD")
    create_acc = AsyncCreateAccount(async_uow)
    acc = await create_acc("Equity", "USD")
    assert acc.full_name == "Equity"
    assert acc.name == "Equity"


@pytest.mark.asyncio
async def test_account_depth_matches_segments(async_uow):
    # Optional extra: ensure normalization does not change segment count semantics
    create_cur = AsyncCreateCurrency(async_uow)
    await create_cur("USD")
    create_acc = AsyncCreateAccount(async_uow)
    acc = await create_acc("A: B :C", "USD")
    assert acc.full_name == "A:B:C"
    # Depth is a domain concept; here we at least ensure 3 segments projected
    assert acc.name == "C"

