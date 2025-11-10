from __future__ import annotations

from abc import abstractmethod
from datetime import datetime
from decimal import Decimal
from typing import Any, Protocol, runtime_checkable

from sqlalchemy.ext.asyncio import AsyncSession

from application.dto.models import (
    AccountDTO,
    CurrencyDTO,
    ExchangeRateEventDTO,
    RichTransactionDTO,
    TradingBalanceDTO,
    TransactionDTO,
)


@runtime_checkable
class Clock(Protocol):
    """Абстракция времени для тестов / детерминированности."""
    def now(self) -> datetime: ...


@runtime_checkable
class BalanceRepository(Protocol):
    """Кэш балансов по счетам.

    Контракт минимален и не навязывает форму хранения.
    amount — накопленный баланс, last_ts — момент времени, до которого кэш консистентен.
    """

    def upsert_cache(self, account_full_name: str, amount: Decimal, last_ts: datetime) -> None: ...
    def get_cache(self, account_full_name: str) -> tuple[Decimal, datetime] | None: ...
    def clear(self, account_full_name: str) -> None: ...


@runtime_checkable
class ExchangeRateEventsRepository(Protocol):
    """Audit trail of exchange rate updates.

    Events are append-only; repository provides listing (filtered by code, limited) and insertion.
    Listing ordering: newest first (occurred_at DESC, id DESC).
    TTL/archival support: list_old_events/delete/archive/move in batches.
    """
    def add_event(self, code: str, rate: Decimal, occurred_at: datetime, policy_applied: str, source: str | None) -> ExchangeRateEventDTO: ...
    def list_events(self, code: str | None = None, limit: int | None = None) -> list[ExchangeRateEventDTO]: ...
    # New TTL helpers
    def list_old_events(self, cutoff: datetime, limit: int) -> list[ExchangeRateEventDTO]: ...
    def delete_events_by_ids(self, ids: list[int]) -> int: ...
    def archive_events(self, rows: list[ExchangeRateEventDTO], archived_at: datetime) -> int: ...
    def move_events_to_archive(self, cutoff: datetime, limit: int, archived_at: datetime) -> tuple[int, int]: ...  # (archived, deleted)


@runtime_checkable
class UnitOfWork(Protocol):
    """Транзакционная граница приложения."""

    @property
    @abstractmethod
    def accounts(self) -> AccountRepository: ...

    @property
    @abstractmethod
    def currencies(self) -> CurrencyRepository: ...

    @property
    @abstractmethod
    def transactions(self) -> TransactionRepository: ...

    # Optional balances repo (required for SQL balance caching scenarios)
    @property
    def balances(self) -> BalanceRepository: ...  # type: ignore[override]
    # Optional FX audit events repository
    @property
    def exchange_rate_events(self) -> ExchangeRateEventsRepository: ...  # type: ignore[override]

    def commit(self) -> None: ...
    def rollback(self) -> None: ...


@runtime_checkable
class CurrencyRepository(Protocol):
    def get_by_code(self, code: str) -> CurrencyDTO | None: ...
    def upsert(self, dto: CurrencyDTO) -> CurrencyDTO: ...
    def list_all(self) -> list[CurrencyDTO]: ...
    # Base currency helpers
    def get_base(self) -> CurrencyDTO | None: ...
    def set_base(self, code: str) -> None: ...
    def clear_base(self) -> None: ...
    # Optional optimization for SQL adapter
    def bulk_upsert_rates(self, updates: list[tuple[str, Decimal]]) -> None: ...


@runtime_checkable
class AccountRepository(Protocol):
    def get_by_full_name(self, full_name: str) -> AccountDTO | None: ...
    def create(self, dto: AccountDTO) -> AccountDTO: ...
    def list(self, parent_id: str | None = None) -> list[AccountDTO]: ...


@runtime_checkable
class TransactionRepository(Protocol):
    def add(self, dto: TransactionDTO) -> TransactionDTO: ...
    def list_between(self, start: datetime, end: datetime, meta: dict[str, Any] | None = None) -> list[TransactionDTO]: ...
    def aggregate_trading_balance(self, as_of: datetime, base_currency: str | None = None) -> TradingBalanceDTO: ...
    def ledger(
        self,
        account_full_name: str,
        start: datetime,
        end: datetime,
        meta: dict[str, Any] | None = None,
        *,
        offset: int = 0,
        limit: int | None = None,
        order: str = "ASC",
    ) -> list[RichTransactionDTO]: ...
    def account_balance(self, account_full_name: str, as_of: datetime) -> Decimal: ...


# ===================== ASYNC Protocols (ASYNC-05) =====================


@runtime_checkable
class SupportsCommitRollback(Protocol):
    """Common minimal transaction interface used by both sync and async UoWs.

    Purpose:
    - Provide a tiny shared contract for components that need to trigger
      persistence of changes without binding to a specific UoW implementation.

    Methods:
    - commit(): persist current transaction changes.
    - rollback(): revert current transaction changes.

    Notes:
    - Async UoWs expose async commit/rollback; this Protocol is informational
      and is not meant for isinstance checks across sync/async boundaries.
    """

    def commit(self) -> Any:  # return type may vary (None or Awaitable[None])
        """Commit current transaction."""
        ...

    def rollback(self) -> Any:  # return type may vary (None or Awaitable[None])
        """Rollback current transaction."""
        ...


@runtime_checkable
class AsyncCurrencyRepository(Protocol):
    """Async access to currencies with semantics matching sync repository.

    Methods:
    - get_by_code(code): return CurrencyDTO or None.
    - upsert(dto): create or update a currency, enforcing base uniqueness.
    - list_all(): list all currencies.
    - get_base(): return base currency or None.
    - set_base(code): set specified currency as base; may raise ValueError.
    - clear_base(): clear base flag from all currencies.
    - bulk_upsert_rates(updates): update non-base exchange rates in batch.

    Returns:
    - DTO instances typed from application.dto.models.

    Raises:
    - ValueError on invalid operations like setting base for non-existing code.
    """

    async def get_by_code(self, code: str) -> CurrencyDTO | None:  # noqa: D401 - short doc in class
        """Return currency by code or None."""
        ...

    async def upsert(self, dto: CurrencyDTO) -> CurrencyDTO:
        """Create or update a currency and return resulting DTO."""
        ...

    async def list_all(self) -> list[CurrencyDTO]:
        """Return all currencies as a list of DTOs."""
        ...

    async def get_base(self) -> CurrencyDTO | None:
        """Return base currency DTO or None if not set."""
        ...

    async def set_base(self, code: str) -> None:
        """Mark specified currency as base, clearing others."""
        ...

    async def clear_base(self) -> None:
        """Clear base flag from all currencies."""
        ...

    async def bulk_upsert_rates(self, updates: list[tuple[str, Decimal]]) -> None:
        """Batch upsert exchange rates for non-base currencies."""
        ...


@runtime_checkable
class AsyncAccountRepository(Protocol):
    """Async access to account catalog.

    Methods:
    - get_by_full_name(name): return AccountDTO or None.
    - create(dto): create a new account; may raise ValueError on duplicates.
    - list(parent_id?): list accounts (parent filter optional, parity with sync).
    """

    async def get_by_full_name(self, full_name: str) -> AccountDTO | None:
        """Return account DTO by full name or None."""
        ...

    async def create(self, dto: AccountDTO) -> AccountDTO:
        """Create a new account and return DTO; enforce unique full_name."""
        ...

    async def list(self, parent_id: str | None = None) -> list[AccountDTO]:
        """Return all accounts; parent filter may be ignored by adapter."""
        ...


@runtime_checkable
class AsyncBalanceRepository(Protocol):
    """Async balance cache operations per account.

    Methods:
    - upsert_cache(account_full_name, amount, last_ts)
    - get_cache(account_full_name) -> (amount, last_ts) | None
    - clear(account_full_name)
    """

    async def upsert_cache(self, account_full_name: str, amount: Decimal, last_ts: datetime) -> None:
        """Insert or update balance cache for account."""
        ...

    async def get_cache(self, account_full_name: str) -> tuple[Decimal, datetime] | None:
        """Return cached (amount, ts) for account or None."""
        ...

    async def clear(self, account_full_name: str) -> None:
        """Clear cached balance for account if present."""
        ...


@runtime_checkable
class AsyncTransactionRepository(Protocol):
    """Async repository for transactions and derived queries.

    Methods mirror sync variant, but are awaitable.
    """

    async def add(self, dto: TransactionDTO) -> TransactionDTO:
        """Insert a new transaction and return DTO."""
        ...

    async def list_between(
        self, start: datetime, end: datetime, meta: dict[str, Any] | None = None
    ) -> list[TransactionDTO]:
        """List transactions between timestamps, filtered by meta if provided."""
        ...

    async def aggregate_trading_balance(self, as_of: datetime, base_currency: str | None = None) -> TradingBalanceDTO:
        """Aggregate debit/credit totals per currency and return DTO."""
        ...

    async def ledger(
        self,
        account_full_name: str,
        start: datetime,
        end: datetime,
        meta: dict[str, Any] | None = None,
        *,
        offset: int = 0,
        limit: int | None = None,
        order: str = "ASC",
    ) -> list[RichTransactionDTO]:
        """Return ledger entries for account with ordering/pagination."""
        ...

    async def account_balance(self, account_full_name: str, as_of: datetime) -> Decimal:
        """Compute account balance at a point in time."""
        ...


@runtime_checkable
class AsyncExchangeRateEventsRepository(Protocol):
    """Async audit trail for FX exchange rate events with TTL helpers.

    Methods:
    - add_event(...): append new event and return DTO.
    - list_events(code?, limit?): newest-first listing, optional filter.
    - list_old_events(cutoff, limit): oldest-first pagination for TTL.
    - delete_events_by_ids(ids): delete by PKs, return count.
    - archive_events(rows, archived_at): copy rows to archive, return count.
    - move_events_to_archive(cutoff, limit, archived_at): two-phase archive; returns (archived, deleted).
    """

    async def add_event(
        self, code: str, rate: Decimal, occurred_at: datetime, policy_applied: str, source: str | None
    ) -> ExchangeRateEventDTO:
        """Insert new FX event and return DTO."""
        ...

    async def list_events(self, code: str | None = None, limit: int | None = None) -> list[ExchangeRateEventDTO]:
        """List FX events filtered by code (optional), newest first."""
        ...

    async def list_old_events(self, cutoff: datetime, limit: int) -> list[ExchangeRateEventDTO]:
        """List events strictly older than cutoff, oldest first, up to limit."""
        ...

    async def delete_events_by_ids(self, ids: list[int]) -> int:
        """Delete events by ids; return number of deleted rows (>= 0)."""
        ...

    async def archive_events(self, rows: list[ExchangeRateEventDTO], archived_at: datetime) -> int:
        """Archive provided events; return number of archived rows (>= 0)."""
        ...

    async def move_events_to_archive(self, cutoff: datetime, limit: int, archived_at: datetime) -> tuple[int, int]:
        """Move old events into archive in batches; return (archived, deleted)."""
        ...


@runtime_checkable
class AsyncUnitOfWork(Protocol):
    """Async transactional boundary for application code.

    Purpose:
    - Provide an awaitable context manager over an ``AsyncSession`` with lazy
      access to async repositories.

    Methods:
    - __aenter__/__aexit__: open/close session with commit/rollback semantics.
    - commit/rollback: explicit transaction control inside the context.

    Properties:
    - session: the active SQLAlchemy ``AsyncSession``; only valid inside context.
    - accounts, currencies, transactions, balances, exchange_rate_events:
      async repositories bound to the current session.

    Raises:
    - RuntimeError on repository/session access outside of active context (by implementations).
    """

    # context manager
    async def __aenter__(self) -> AsyncUnitOfWork:
        """Enter async context and return self."""
        ...

    async def __aexit__(self, exc_type, exc: BaseException | None, tb: Any) -> None:
        """Exit async context; commit on success or rollback on error."""
        ...

    async def commit(self) -> None:
        """Explicitly commit current transaction."""
        ...

    async def rollback(self) -> None:
        """Explicitly rollback current transaction."""
        ...

    @property
    def session(self) -> AsyncSession | Any:
        """Return active AsyncSession (implementations may narrow the type)."""
        ...

    # repositories
    @property
    def accounts(self) -> AsyncAccountRepository:  # noqa: D401 - short doc in class
        """Async accounts repository."""
        ...

    @property
    def currencies(self) -> AsyncCurrencyRepository:
        """Async currencies repository."""
        ...

    @property
    def transactions(self) -> AsyncTransactionRepository:
        """Async transactions repository."""
        ...

    @property
    def balances(self) -> AsyncBalanceRepository:
        """Async balances repository (optional in some adapters)."""
        ...

    @property
    def exchange_rate_events(self) -> AsyncExchangeRateEventsRepository:  # type: ignore[override]
        """Async FX audit events repository (optional in some adapters)."""
        ...

