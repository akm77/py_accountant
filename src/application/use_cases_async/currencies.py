from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from application.dto.models import CurrencyDTO
from application.interfaces.ports import AsyncUnitOfWork
from domain.currencies import BaseCurrencyRule, Currency


@dataclass(slots=True)
class AsyncCreateCurrency:
    """Create or update a currency using domain validation.

    Business rules:
    - Validate/normalize code via domain Currency (upper, length 3..10).
    - If exchange_rate is provided, validate via domain (>0, quantized to 6dp).
    - Base currency must keep exchange_rate=None (invariant).

    Repository remains CRUD-only; this use case decides desired state.
    """

    uow: AsyncUnitOfWork

    async def __call__(self, code: str, exchange_rate: Decimal | None = None) -> CurrencyDTO:
        """Create or update a currency and return resulting DTO.

        Raises ValidationError on invalid code or non-positive exchange_rate.
        """
        # Domain validation/normalization
        dom = Currency(code=code)
        q_rate: Decimal | None = None
        if exchange_rate is not None:
            q_rate = dom.set_rate(exchange_rate)

        # Check existing state
        existing = await self.uow.currencies.get_by_code(dom.code)
        if existing:
            # Base currency never stores a rate
            if existing.is_base:
                return existing  # ignore provided rate per invariant
            # Non-base: update rate only if provided
            if q_rate is not None:
                existing.exchange_rate = q_rate
                return await self.uow.currencies.upsert(existing)
            return existing

        # New currency: persist DTO based on domain projection (non-base by default)
        dto = CurrencyDTO(code=dom.code, exchange_rate=q_rate, is_base=False)
        return await self.uow.currencies.upsert(dto)


@dataclass(slots=True)
class AsyncSetBaseCurrency:
    """Select and persist a single base currency via domain rule.

    Uses BaseCurrencyRule.ensure_single_base to validate presence and mark only
    one base in-memory, then persists using CRUD operations (Variant B):
    clear_base() then upsert() the target with is_base=True and rate cleared.
    """

    uow: AsyncUnitOfWork

    async def __call__(self, code: str) -> None:
        """Set specified currency as the single base.

        Raises ValidationError if the currency code is not present.
        """
        # Load and project repository state into domain objects
        rows = await self.uow.currencies.list_all()
        domain_currencies: list[Currency] = []
        for r in rows:
            # Validate each code and rate through domain constructor
            domain_currencies.append(
                Currency(code=r.code, is_base=r.is_base, rate_to_base=r.exchange_rate)
            )

        # Domain rule: ensure exactly one base (idempotent if same)
        target = BaseCurrencyRule.ensure_single_base(domain_currencies, code)

        # Persist desired state with CRUD ops only: clear all base flags, then set target as base
        await self.uow.currencies.clear_base()
        await self.uow.currencies.upsert(
            CurrencyDTO(code=target.code, is_base=True, exchange_rate=None)
        )


@dataclass(slots=True)
class AsyncListCurrencies:
    """List all currencies as-is from repository (passthrough)."""

    uow: AsyncUnitOfWork

    async def __call__(self) -> list[CurrencyDTO]:  # noqa: D401 - simple passthrough
        """Return a list of all currencies (possibly empty)."""
        return await self.uow.currencies.list_all()
