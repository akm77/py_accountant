from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from application.dto.models import CurrencyDTO
from application.interfaces.ports import AsyncUnitOfWork


@dataclass(slots=True)
class AsyncCreateCurrency:
    """Purpose:
    Create a currency if absent or update its exchange rate if it exists.

    Parameters:
    - uow: AsyncUnitOfWork providing access to ``currencies`` repository.
    - code: ISO-like currency code (case-insensitive normalized by repository).
    - exchange_rate: Optional decimal rate relative to base currency; ignored if
      setting the currency as base.

    Returns:
    - CurrencyDTO with possibly updated ``exchange_rate``.

    Raises:
    - ValueError: if repository upsert encounters invalid state (e.g., base rules).

    Notes:
    - If the currency already exists and ``exchange_rate`` is provided, it's
      overwritten (unless base). Base currency has ``exchange_rate=None``.
    """
    uow: AsyncUnitOfWork

    async def __call__(self, code: str, exchange_rate: Decimal | None = None) -> CurrencyDTO:
        """Create or update currency and return resulting DTO."""
        existing = await self.uow.currencies.get_by_code(code)
        if existing:
            if exchange_rate is not None and not existing.is_base:
                existing.exchange_rate = exchange_rate
                return await self.uow.currencies.upsert(existing)
            return existing
        dto = CurrencyDTO(code=code)
        if exchange_rate is not None:
            dto.exchange_rate = exchange_rate
        return await self.uow.currencies.upsert(dto)


@dataclass(slots=True)
class AsyncSetBaseCurrency:
    """Purpose:
    Mark the specified currency as base, ensuring uniqueness.

    Parameters:
    - uow: AsyncUnitOfWork.
    - code: Currency code to mark as base.

    Returns:
    - None.

    Raises:
    - ValueError: if currency does not exist (propagated from repository).

    Notes:
    - Exchange rate for base currency will be set to ``None``.
    """
    uow: AsyncUnitOfWork

    async def __call__(self, code: str) -> None:
        """Set specified currency as base; propagate repository errors."""
        await self.uow.currencies.set_base(code)


@dataclass(slots=True)
class AsyncListCurrencies:
    """Purpose:
    List all currencies currently stored.

    Parameters:
    - uow: AsyncUnitOfWork.

    Returns:
    - list[CurrencyDTO]: possibly empty list in unspecified order.

    Raises:
    - None.

    Notes:
    - Caller may sort/filter externally; repository returns raw set.
    """
    uow: AsyncUnitOfWork

    async def __call__(self) -> list[CurrencyDTO]:  # noqa: D401 - simple passthrough
        """Return a list of all currencies (possibly empty)."""
        return await self.uow.currencies.list_all()
