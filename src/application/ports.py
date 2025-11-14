from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Protocol, runtime_checkable

from sqlalchemy.ext.asyncio import AsyncSession

from application.dto.models import (
    AccountDTO,
    CurrencyDTO,
    ExchangeRateEventDTO,
    RichTransactionDTO,
    TransactionDTO,
)

__all__ = [
    "Clock",
    "SupportsCommitRollback",
    "AsyncCurrencyRepository",
    "AsyncAccountRepository",
    "AsyncTransactionRepository",
    "AsyncExchangeRateEventsRepository",
    "AsyncUnitOfWork",
]


@runtime_checkable
class Clock(Protocol):
    """Clock abstraction to decouple time in tests.

    Implementations typically return timezone-aware UTC datetimes.
    """

    def now(self) -> datetime: ...


@runtime_checkable
class SupportsCommitRollback(Protocol):
    """Minimal contract for components that can commit/rollback.

    Note: Async UoWs expose async commit/rollback; this Protocol is informational
    only and allows loose coupling in higher-level code.
    """

    def commit(self) -> Any: ...  # may be None or Awaitable[None]
    def rollback(self) -> Any: ...  # may be None or Awaitable[None]


@runtime_checkable
class AsyncCurrencyRepository(Protocol):
    """Async access to currency catalog and base helpers."""

    async def get_by_code(self, code: str) -> CurrencyDTO | None: ...
    async def upsert(self, dto: CurrencyDTO) -> CurrencyDTO: ...
    async def list_all(self) -> list[CurrencyDTO]: ...
    async def get_base(self) -> CurrencyDTO | None: ...
    async def set_base(self, code: str) -> None: ...
    async def clear_base(self) -> None: ...
    async def bulk_upsert_rates(self, updates: list[tuple[str, Decimal]]) -> None: ...


@runtime_checkable
class AsyncAccountRepository(Protocol):
    """Async access to account catalog."""

    async def get_by_full_name(self, full_name: str) -> AccountDTO | None: ...
    async def create(self, dto: AccountDTO) -> AccountDTO: ...
    async def list(self, parent_id: str | None = None) -> list[AccountDTO]: ...


@runtime_checkable
class AsyncTransactionRepository(Protocol):
    """Async repository for transactions and derived queries (CRUD + ledger)."""

    async def add(self, dto: TransactionDTO) -> TransactionDTO: ...
    async def list_between(self, start: datetime, end: datetime, meta: dict[str, Any] | None = None) -> list[TransactionDTO]: ...
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
    ) -> list[RichTransactionDTO]: ...


@runtime_checkable
class AsyncExchangeRateEventsRepository(Protocol):
    """Async audit trail for exchange rate events with TTL helpers."""

    async def add_event(
        self, code: str, rate: Decimal, occurred_at: datetime, policy_applied: str, source: str | None
    ) -> ExchangeRateEventDTO: ...
    async def list_events(self, code: str | None = None, limit: int | None = None) -> list[ExchangeRateEventDTO]: ...
    async def list_old_events(self, cutoff: datetime, limit: int) -> list[ExchangeRateEventDTO]: ...
    async def delete_events_by_ids(self, ids: list[int]) -> int: ...
    async def archive_events(self, rows: list[ExchangeRateEventDTO], archived_at: datetime) -> int: ...
    async def move_events_to_archive(self, cutoff: datetime, limit: int, archived_at: datetime) -> tuple[int, int]: ...


@runtime_checkable
class AsyncUnitOfWork(Protocol):
    """Async transactional boundary for application code.

    Provides an awaitable context manager over an AsyncSession with access to
    async repositories bound to the current session.
    """

    # context manager
    async def __aenter__(self) -> AsyncUnitOfWork: ...
    async def __aexit__(self, exc_type, exc: BaseException | None, tb: Any) -> None: ...

    async def commit(self) -> None: ...
    async def rollback(self) -> None: ...

    @property
    def session(self) -> AsyncSession | Any: ...

    # repositories
    @property
    def accounts(self) -> AsyncAccountRepository: ...

    @property
    def currencies(self) -> AsyncCurrencyRepository: ...

    @property
    def transactions(self) -> AsyncTransactionRepository: ...

    @property
    def exchange_rate_events(self) -> AsyncExchangeRateEventsRepository: ...
