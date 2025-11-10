from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from application.dto.models import ExchangeRateEventDTO
from application.interfaces.ports import AsyncUnitOfWork


@dataclass(slots=True)
class AsyncAddExchangeRateEvent:
    """Purpose:
    Append an FX exchange rate event to the audit log.

    Parameters:
    - uow: AsyncUnitOfWork.
    - code: Currency code affected.
    - rate: Effective rate applied.
    - occurred_at: Timestamp of event occurrence.
    - policy_applied: Description/key of policy applied.
    - source: Optional external source tag.

    Returns:
    - ExchangeRateEventDTO for the inserted event.

    Raises:
    - ValueError: if repository validates and rejects data (e.g. missing code format).

    Notes:
    - No de-duplication is performed; events are append-only.
    """
    uow: AsyncUnitOfWork

    async def __call__(
        self,
        code: str,
        rate: Decimal,
        occurred_at: datetime,
        policy_applied: str,
        source: str | None = None,
    ) -> ExchangeRateEventDTO:
        """Insert FX rate event row and return DTO."""
        return await self.uow.exchange_rate_events.add_event(code, rate, occurred_at, policy_applied, source)


@dataclass(slots=True)
class AsyncListExchangeRateEvents:
    """Purpose:
    List recent FX exchange rate events optionally filtered by code and limited.

    Parameters:
    - uow: AsyncUnitOfWork.
    - code: Optional currency code filter.
    - limit: Optional maximum number of events to return; negative -> empty list.

    Returns:
    - list[ExchangeRateEventDTO].

    Raises:
    - None.

    Notes:
    - Ordering is newest-first per repository semantics.
    """
    uow: AsyncUnitOfWork

    async def __call__(self, code: str | None = None, limit: int | None = None) -> list[ExchangeRateEventDTO]:
        """Return FX events list filtered by code and limited if provided."""
        return await self.uow.exchange_rate_events.list_events(code, limit)
