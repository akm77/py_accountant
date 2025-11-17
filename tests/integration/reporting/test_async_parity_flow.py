from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from application.use_cases_async import (
    AsyncCreateCurrency,
    AsyncGetParityReport,
    AsyncSetBaseCurrency,
)


@pytest.mark.asyncio
async def test_async_parity_flow_with_base_and_two_currencies(async_uow):
    class _Clock:
        def now(self):
            return datetime(2025, 11, 12, 12, 0, 0, tzinfo=UTC)

    clock = _Clock()
    await AsyncCreateCurrency(async_uow)("USD")
    await AsyncSetBaseCurrency(async_uow)("USD")
    await AsyncCreateCurrency(async_uow)("EUR", exchange_rate=Decimal("1.10"))
    await AsyncCreateCurrency(async_uow)("JPY", exchange_rate=Decimal("150"))

    rep = await AsyncGetParityReport(async_uow, clock)(include_dev=True)
    codes = [line.currency_code for line in rep.lines]
    assert codes == ["EUR", "JPY", "USD"]
    # Deviation for non-base lines present
    eur = next(line for line in rep.lines if line.currency_code == "EUR")
    jpy = next(line for line in rep.lines if line.currency_code == "JPY")
    assert eur.deviation_pct is not None and jpy.deviation_pct is not None


@pytest.mark.asyncio
async def test_async_parity_flow_codes_filter(async_uow):
    class _Clock:
        def now(self):
            return datetime(2025, 11, 12, 12, 0, 0, tzinfo=UTC)

    clock = _Clock()
    await AsyncCreateCurrency(async_uow)("USD")
    await AsyncSetBaseCurrency(async_uow)("USD")
    await AsyncCreateCurrency(async_uow)("EUR", exchange_rate=Decimal("1.10"))
    await AsyncCreateCurrency(async_uow)("JPY", exchange_rate=Decimal("150"))

    rep = await AsyncGetParityReport(async_uow, clock)(codes=["JPY", "usd"])
    assert [line.currency_code for line in rep.lines] == ["JPY", "USD"]
