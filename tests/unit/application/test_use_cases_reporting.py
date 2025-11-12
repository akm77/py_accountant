from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from application.dto.models import EntryLineDTO, ParityReportDTO, TradingBalanceSnapshotDTO
from application.use_cases_async import (
    AsyncCreateAccount,
    AsyncCreateCurrency,
    AsyncGetParityReport,
    AsyncGetTradingBalanceSnapshotReport,
    AsyncPostTransaction,
    AsyncSetBaseCurrency,
)
from domain.errors import ValidationError


class _Clock:
    def __init__(self, now_dt: datetime | None = None) -> None:
        self._now = now_dt or datetime.now(UTC)

    def now(self) -> datetime:
        return self._now


@pytest.mark.asyncio
async def test_parity_report_empty_returns_empty_lines(async_uow):
    clock = _Clock()
    report = await AsyncGetParityReport(async_uow, clock)()
    assert isinstance(report, ParityReportDTO)
    assert report.lines == [] and report.base_currency is None and report.has_deviation is False


@pytest.mark.asyncio
async def test_parity_report_base_only_includes_single_base(async_uow):
    clock = _Clock()
    await AsyncCreateCurrency(async_uow)("USD")
    await AsyncSetBaseCurrency(async_uow)("USD")
    rep = await AsyncGetParityReport(async_uow, clock)(base_only=True)
    assert rep.total_currencies == 1
    assert rep.lines[0].currency_code == "USD" and rep.lines[0].is_base is True


@pytest.mark.asyncio
async def test_parity_report_filters_by_codes_subset(async_uow):
    clock = _Clock()
    await AsyncCreateCurrency(async_uow)("USD")
    await AsyncCreateCurrency(async_uow)("EUR", exchange_rate=Decimal("1.10"))
    await AsyncCreateCurrency(async_uow)("JPY", exchange_rate=Decimal("150"))
    await AsyncSetBaseCurrency(async_uow)("USD")
    rep = await AsyncGetParityReport(async_uow, clock)(codes=["eur", "usd", "usd", "invalid", "  "])
    codes_out = [l.currency_code for l in rep.lines]
    assert codes_out == ["EUR", "USD"]


@pytest.mark.asyncio
async def test_parity_report_deviation_flag_when_include_dev(async_uow):
    clock = _Clock()
    await AsyncCreateCurrency(async_uow)("USD")
    await AsyncCreateCurrency(async_uow)("EUR", exchange_rate=Decimal("1.2500"))
    await AsyncSetBaseCurrency(async_uow)("USD")
    rep = await AsyncGetParityReport(async_uow, clock)(include_dev=True)
    eur_line = next(l for l in rep.lines if l.currency_code == "EUR")
    assert eur_line.deviation_pct == Decimal("25.00")  # (1.25 - 1) * 100
    assert rep.has_deviation is True


@pytest.mark.asyncio
async def test_parity_report_no_deviation_when_flag_false(async_uow):
    clock = _Clock()
    await AsyncCreateCurrency(async_uow)("USD")
    await AsyncCreateCurrency(async_uow)("EUR", exchange_rate=Decimal("1.2500"))
    await AsyncSetBaseCurrency(async_uow)("USD")
    rep = await AsyncGetParityReport(async_uow, clock)(include_dev=False)
    assert all(l.deviation_pct is None for l in rep.lines)
    assert rep.has_deviation is False


@pytest.mark.asyncio
async def test_parity_report_handles_missing_base_currency(async_uow):
    clock = _Clock()
    await AsyncCreateCurrency(async_uow)("EUR", exchange_rate=Decimal("1.10"))
    # No base set
    rep = await AsyncGetParityReport(async_uow, clock)()
    assert rep.base_currency is None
    assert all(l.deviation_pct is None for l in rep.lines)


@pytest.mark.asyncio
async def test_parity_report_invalid_codes_ignored_or_validation_error(async_uow):
    clock = _Clock()
    await AsyncCreateCurrency(async_uow)("USD")
    await AsyncSetBaseCurrency(async_uow)("USD")
    # Non-list codes should raise ValidationError
    with pytest.raises(ValidationError):
        await AsyncGetParityReport(async_uow, clock)(codes="USD")  # type: ignore[arg-type]
    # Mixed invalid entries ignored
    rep = await AsyncGetParityReport(async_uow, clock)(codes=["usd", 123, None, "", "USD"])  # type: ignore[list-item]
    assert [l.currency_code for l in rep.lines] == ["USD"]


@pytest.mark.asyncio
async def test_trading_balance_snapshot_raw_mode_empty(async_uow):
    clock = _Clock()
    snap = await AsyncGetTradingBalanceSnapshotReport(async_uow, clock)(detailed=False)
    assert isinstance(snap, TradingBalanceSnapshotDTO)
    assert snap.lines_raw == [] and snap.lines_detailed is None and snap.mode == "raw"


@pytest.mark.asyncio
async def test_trading_balance_snapshot_detailed_requires_base_or_rates(async_uow):
    clock = _Clock()
    # No base set; detailed should raise ValidationError through underlying detailed use case
    with pytest.raises(ValidationError):
        await AsyncGetTradingBalanceSnapshotReport(async_uow, clock)(detailed=True)


@pytest.mark.asyncio
async def test_trading_balance_snapshot_raw_and_detailed_flow(async_uow):
    clock = _Clock()
    await AsyncCreateCurrency(async_uow)("USD")
    await AsyncCreateCurrency(async_uow)("EUR", exchange_rate=Decimal("1.10"))
    await AsyncSetBaseCurrency(async_uow)("USD")
    await AsyncCreateAccount(async_uow)("Assets:CashUSD", "USD")
    await AsyncCreateAccount(async_uow)("Assets:CashEUR", "EUR")
    post = AsyncPostTransaction(async_uow, clock)
    await post([
        EntryLineDTO(side="DEBIT", account_full_name="Assets:CashUSD", amount=Decimal("5"), currency_code="USD"),
        EntryLineDTO(side="CREDIT", account_full_name="Assets:CashUSD", amount=Decimal("5"), currency_code="USD"),
    ])
    await post([
        EntryLineDTO(side="DEBIT", account_full_name="Assets:CashEUR", amount=Decimal("3"), currency_code="EUR"),
        EntryLineDTO(side="CREDIT", account_full_name="Assets:CashEUR", amount=Decimal("3"), currency_code="EUR"),
    ])
    raw_snap = await AsyncGetTradingBalanceSnapshotReport(async_uow, clock)(detailed=False)
    det_snap = await AsyncGetTradingBalanceSnapshotReport(async_uow, clock)(detailed=True)
    assert raw_snap.lines_raw and det_snap.lines_detailed
    assert raw_snap.mode == "raw" and det_snap.mode == "detailed"
