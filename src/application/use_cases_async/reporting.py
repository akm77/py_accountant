from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from application.dto.models import (
    ParityLineDTO,
    ParityReportDTO,
    TradingBalanceLineDetailed,
    TradingBalanceLineSimple,
    TradingBalanceSnapshotDTO,
)
from application.interfaces.ports import AsyncUnitOfWork, Clock
from domain.errors import ValidationError

from .trading_balance import AsyncGetTradingBalanceDetailed, AsyncGetTradingBalanceRaw

__all__ = ["AsyncGetParityReport", "AsyncGetTradingBalanceSnapshotReport"]


def _epoch_with_tz(now: datetime) -> datetime:
    return datetime.fromtimestamp(0, tz=now.tzinfo)


@dataclass(slots=True)
class AsyncGetParityReport:
    """Build a parity report snapshot for selected currencies.

    Args:
        base_only: If True, include only the detected base currency (empty if none).
        codes: Optional list of currency codes to filter (case-insensitive, duplicates trimmed; invalid/empty ignored).
        include_dev: If True and base exists, compute deviation_pct heuristic for non-base rows.
    Returns:
        ParityReportDTO with lines (possibly empty), base_currency (or None) and has_deviation flag.
    Notes:
        Deviation heuristic: (latest_rate - 1) * 100 where base parity is 1.0. Placeholder for future domain service.
    """

    uow: AsyncUnitOfWork
    clock: Clock

    async def __call__(
        self,
        *,
        base_only: bool = False,
        codes: list[str] | None = None,
        include_dev: bool = True,
    ) -> ParityReportDTO:
        # Validate codes type early
        if codes is not None and not isinstance(codes, list):
            raise ValidationError("codes must be a list of strings or None")

        # Load currencies (CRUD-only)
        cur_dtos = await self.uow.currencies.list_all()
        base_dto = next((c for c in cur_dtos if c.is_base), None)
        base_code = base_dto.code if base_dto else None

        # Normalize filter set
        filter_set: set[str] | None = None
        if codes is not None:
            norm: set[str] = set()
            for raw in codes:
                if not isinstance(raw, str):
                    # Ignore non-string entries silently (soft behavior)
                    continue
                code = raw.strip().upper()
                if not code:  # ignore empty
                    continue
                norm.add(code)
            filter_set = norm

        # If base_only requested: return only base (if exists and passes code filter)
        lines: list[ParityLineDTO] = []
        if base_only:
            if base_dto and (filter_set is None or base_dto.code in filter_set):
                lines.append(
                    ParityLineDTO(
                        currency_code=base_dto.code,
                        is_base=True,
                        latest_rate=None,
                        deviation_pct=None,
                    )
                )
        else:
            # Build lines for all currencies respecting optional filter
            for dto in cur_dtos:
                if filter_set is not None and dto.code not in filter_set:
                    continue
                is_base = dto.is_base
                latest_rate = None if is_base else dto.exchange_rate
                deviation: Decimal | None = None
                if include_dev and base_code and not is_base and latest_rate is not None:
                    # Heuristic relative to parity 1.0; no quantization by design (keep raw precision)
                    deviation = (latest_rate - Decimal("1")) * Decimal("100")
                # If base missing, deviation stays None per spec
                lines.append(
                    ParityLineDTO(
                        currency_code=dto.code,
                        is_base=is_base,
                        latest_rate=latest_rate,
                        deviation_pct=deviation,
                    )
                )

        # Deterministic ordering: sort by currency_code ASC
        lines.sort(key=lambda line: line.currency_code)
        now = self.clock.now()
        report = ParityReportDTO(
            generated_at=now,
            base_currency=base_code,
            lines=lines,
            total_currencies=len(lines),
            has_deviation=any(line.deviation_pct is not None for line in lines),
        )
        return report


@dataclass(slots=True)
class AsyncGetTradingBalanceSnapshotReport:
    """Produce trading balance snapshot in raw or detailed mode.

    Args:
        as_of: Optional timestamp limiting inclusive end of window (defaults clock.now()).
        detailed: If True, include converted base amounts (detailed mode); else raw mode.
    Returns:
        TradingBalanceSnapshotDTO with appropriate list populated and mode flag.
    Notes:
        Start of window defaults to epoch with same tz as ``clock.now()``; future iterations may accept explicit window.
    """

    uow: AsyncUnitOfWork
    clock: Clock

    async def __call__(
        self,
        *,
        as_of: datetime | None = None,
        detailed: bool = False,
    ) -> TradingBalanceSnapshotDTO:
        now = self.clock.now()
        end_dt = as_of or now
        start_dt = _epoch_with_tz(now)

        base_dto = await self.uow.currencies.get_base()
        base_code = base_dto.code if base_dto else None

        if detailed:
            detailed_lines: list[TradingBalanceLineDetailed] = []
            # Delegate to existing detailed use case (will raise ValidationError if base missing per spec)
            detailed_lines = await AsyncGetTradingBalanceDetailed(self.uow, self.clock)(start=start_dt, end=end_dt)
            return TradingBalanceSnapshotDTO(
                as_of=end_dt,
                lines_raw=None,
                lines_detailed=detailed_lines,
                mode="detailed",
                base_currency=base_code,
            )
        # Raw mode
        raw_lines: list[TradingBalanceLineSimple] = await AsyncGetTradingBalanceRaw(self.uow, self.clock)(
            start=start_dt, end=end_dt
        )
        return TradingBalanceSnapshotDTO(
            as_of=end_dt,
            lines_raw=raw_lines,
            lines_detailed=None,
            mode="raw",
            base_currency=base_code,
        )

