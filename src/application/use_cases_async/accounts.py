from __future__ import annotations

from dataclasses import dataclass

from application.dto.models import AccountDTO
from application.interfaces.ports import AsyncUnitOfWork
from domain.accounts import Account


@dataclass(slots=True)
class AsyncCreateAccount:
    """Create a new account bound to an existing currency.

    Semantic rules:
    - Domain validation & normalization performed via ``Account`` (full_name & currency_code).
    - ``ValidationError``: format/validation issues (invalid full_name, currency_code length).
    - ``ValueError``: missing currency or duplicate account (resource state problems).
    - Repository layer remains CRUD-only (no manual parsing or normalization here).

    Returns ``AccountDTO`` with id populated by repository.
    """
    uow: AsyncUnitOfWork

    async def __call__(self, full_name: str, currency_code: str) -> AccountDTO:
        """Create account ensuring validation, currency existence and uniqueness.

        Args:
            full_name: Hierarchical account path (e.g. "Assets:Cash"). May contain whitespace which is trimmed per segment.
            currency_code: Target currency code (will be normalized to upper case by domain).

        Raises:
            ValidationError: If full_name or currency_code fail domain validation (empty, bad delimiters, length constraints).
            ValueError: If currency does not exist or account with same full_name already exists.
        """
        # Domain validation & normalization (may raise ValidationError)
        account = Account(full_name=full_name, currency_code=currency_code)

        # Verify currency existence (resource lookup)
        cur = await self.uow.currencies.get_by_code(account.currency_code)
        if not cur:
            raise ValueError(f"Currency not found: {account.currency_code}")

        # Ensure uniqueness on normalized full_name
        existing = await self.uow.accounts.get_by_full_name(account.full_name)
        if existing:
            raise ValueError(f"Account already exists: {account.full_name}")

        dto = AccountDTO(
            id="",  # repository assigns id
            name=account.name,
            full_name=account.full_name,
            currency_code=account.currency_code,
            parent_id=None,  # parent_id management out of scope for I16
        )
        return await self.uow.accounts.create(dto)


@dataclass(slots=True)
class AsyncGetAccount:
    """Fetch account by its full_name (passthrough).

    Returns ``AccountDTO`` or ``None`` if not found. No additional validation.
    """
    uow: AsyncUnitOfWork

    async def __call__(self, full_name: str) -> AccountDTO | None:  # noqa: D401 - passthrough
        """Return account by full_name or ``None`` if absent."""
        return await self.uow.accounts.get_by_full_name(full_name)


@dataclass(slots=True)
class AsyncListAccounts:
    """List all accounts (passthrough).

    Returns list of ``AccountDTO``; empty list if none exist.
    """
    uow: AsyncUnitOfWork

    async def __call__(self) -> list[AccountDTO]:  # noqa: D401 - passthrough
        """Return list of existing accounts (possibly empty)."""
        return await self.uow.accounts.list()
