from __future__ import annotations

from decimal import Decimal

import pytest

from py_accountant.application.use_cases_async.currencies import (
    AsyncCreateCurrency,
    AsyncListCurrencies,
    AsyncSetBaseCurrency,
)
from py_accountant.domain.errors import ValidationError
from py_accountant.domain.quantize import rate_quantize

pytestmark = pytest.mark.asyncio


async def test_create_currency_creates_with_rate_via_domain_quantize(async_uow):
    use_case = AsyncCreateCurrency(async_uow)
    # many fractional digits -> domain should quantize to 6 dp
    dto = await use_case("EUR", exchange_rate=Decimal("0.123456789"))
    assert dto.code == "EUR"
    assert dto.is_base is False
    assert dto.exchange_rate == rate_quantize(Decimal("0.123456789"))


async def test_create_currency_invalid_code_raises_validation_error(async_uow):
    use_case = AsyncCreateCurrency(async_uow)
    with pytest.raises(ValidationError):
        await use_case("US")  # too short
    with pytest.raises(ValidationError):
        await use_case("X" * 11)  # too long


async def test_set_base_currency_switches_single_base_no_rate_changes(async_uow):
    create = AsyncCreateCurrency(async_uow)
    # seed two currencies with rates
    await create("USD", exchange_rate=Decimal("1.0000001"))
    await create("EUR", exchange_rate=Decimal("0.9000004"))
    # switch base to EUR
    set_base = AsyncSetBaseCurrency(async_uow)
    await set_base("EUR")
    # list and verify only EUR is base; its rate is None; USD rate unchanged
    lst = AsyncListCurrencies(async_uow)
    rows = await lst()
    by_code = {r.code: r for r in rows}
    assert by_code["EUR"].is_base is True and by_code["EUR"].exchange_rate is None
    assert by_code["USD"].is_base is False
    assert by_code["USD"].exchange_rate == rate_quantize(Decimal("1.0000001"))
    # idempotent second call
    await set_base("EUR")
    rows2 = await lst()
    base_flags = [r.code for r in rows2 if r.is_base]
    assert base_flags == ["EUR"]


async def test_set_base_currency_missing_raises_validation_error(async_uow):
    set_base = AsyncSetBaseCurrency(async_uow)
    with pytest.raises(ValidationError):
        await set_base("NOPE")


async def test_list_currencies_passthrough(async_uow):
    create = AsyncCreateCurrency(async_uow)
    await create("USD", exchange_rate=Decimal("1"))
    await create("JPY")
    lst = AsyncListCurrencies(async_uow)
    rows = await lst()
    assert {r.code for r in rows} >= {"USD", "JPY"}
