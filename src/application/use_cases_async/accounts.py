from __future__ import annotations

from dataclasses import dataclass

from application.dto.models import AccountDTO
from application.interfaces.ports import AsyncUnitOfWork


@dataclass(slots=True)
class AsyncCreateAccount:
    """Purpose:
    Create a new account bound to an existing currency.

    Parameters:
    - uow: AsyncUnitOfWork.
    - full_name: Hierarchical account full name (e.g., "Assets:Cash").
    - currency_code: Existing currency code for the account.

    Returns:
    - AccountDTO for the newly created account.

    Raises:
    - ValueError: if account already exists or currency is missing.

    Notes:
    - Currency existence is verified via repository lookups.
    """
    uow: AsyncUnitOfWork

    async def __call__(self, full_name: str, currency_code: str) -> AccountDTO:
        """Create account; ensure currency exists and full_name is unique."""
        # Validate currency
        cur = await self.uow.currencies.get_by_code(currency_code)
        if not cur:
            raise ValueError(f"Currency not found: {currency_code}")
        # Ensure uniqueness
        existing = await self.uow.accounts.get_by_full_name(full_name)
        if existing:
            raise ValueError(f"Account already exists: {full_name}")
        dto = AccountDTO(id="", name=full_name.split(":")[-1], full_name=full_name, currency_code=currency_code)
        return await self.uow.accounts.create(dto)


@dataclass(slots=True)
class AsyncGetAccount:
    """Purpose:
    Fetch account by full name.

    Parameters:
    - uow: AsyncUnitOfWork.
    - full_name: Account full name.

    Returns:
    - AccountDTO | None: ``None`` if not found.

    Raises:
    - None.

    Notes:
    - Pure passthrough to repository.
    """
    uow: AsyncUnitOfWork

    async def __call__(self, full_name: str) -> AccountDTO | None:  # noqa: D401 - passthrough
        """Return account by full name or None if not found."""
        return await self.uow.accounts.get_by_full_name(full_name)


@dataclass(slots=True)
class AsyncListAccounts:
    """Purpose:
    List all accounts.

    Parameters:
    - uow: AsyncUnitOfWork.

    Returns:
    - list[AccountDTO]: possibly empty list.

    Raises:
    - None.

    Notes:
    - Parity with sync implementation.
    """
    uow: AsyncUnitOfWork

    async def __call__(self) -> list[AccountDTO]:  # noqa: D401 - passthrough
        """Return a list of accounts (possibly empty)."""
        return await self.uow.accounts.list()
