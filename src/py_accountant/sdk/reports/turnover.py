from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select

from application.interfaces.ports import AsyncUnitOfWork, Clock
from infrastructure.persistence.sqlalchemy.models import AccountDailyTurnoverORM

from ..errors import UserInputError, map_exception

__all__ = [
    "DailyTurnoverLine",
    "get_account_daily_turnovers",
]


@dataclass(slots=True, frozen=True)
class DailyTurnoverLine:
    """Daily turnover aggregation line for a single account and day (UTC).

    Fields:
      - account_full_name: hierarchical account name
      - currency_code: account currency code (upper)
      - date_utc: day bucket (UTC midnight)
      - debit_total: Decimal sum of debits for the day
      - credit_total: Decimal sum of credits for the day
      - net: Decimal(debit_total - credit_total)
    """

    account_full_name: str
    currency_code: str
    date_utc: datetime
    debit_total: Decimal
    credit_total: Decimal
    net: Decimal


def _to_utc_day(dt: datetime) -> datetime:
    dt = dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


async def get_account_daily_turnovers(
    uow: AsyncUnitOfWork,
    clock: Clock,
    *,
    start: datetime,
    end: datetime,
    account_full_name: str | None = None,
) -> list[DailyTurnoverLine]:
    """Return daily debit/credit turnovers from denormalized aggregates.

    Contract:
    - Inputs: start/end datetimes (naive treated as UTC), optional account filter.
    - Output: list of DailyTurnoverLine sorted by account_full_name, date_utc ASC.
    - Errors: start > end -> UserInputError; other exceptions mapped via sdk.errors.

    Notes:
    - Uses account_daily_turnovers aggregate (O(n_days)) and does not scan journal lines.
    - For each row, net = debit_total - credit_total is computed in-Python as Decimal.
    """
    try:
        if start is None or end is None:
            raise UserInputError("start and end must be provided")
        start_day = _to_utc_day(start)
        end_day = _to_utc_day(end)
        if start_day > end_day:
            raise UserInputError("start must be <= end")

        stmt = select(AccountDailyTurnoverORM)
        if account_full_name:
            stmt = stmt.where(AccountDailyTurnoverORM.account_full_name == account_full_name)
        stmt = stmt.where(AccountDailyTurnoverORM.date_utc.between(start_day, end_day))
        stmt = stmt.order_by(AccountDailyTurnoverORM.account_full_name.asc(), AccountDailyTurnoverORM.date_utc.asc())

        res = await uow.session.execute(stmt)  # type: ignore[union-attr]
        rows = res.scalars().all()
        out: list[DailyTurnoverLine] = []
        for r in rows:
            net = Decimal(r.debit_total) - Decimal(r.credit_total)
            out.append(
                DailyTurnoverLine(
                    account_full_name=r.account_full_name,
                    currency_code=r.currency_code,
                    date_utc=r.date_utc,
                    debit_total=r.debit_total,
                    credit_total=r.credit_total,
                    net=net,
                )
            )
        return out
    except Exception as exc:
        raise map_exception(exc) from exc

