"""DEPRECATED module: use `application.ports` for async Protocols.

This file remains temporarily (I11..I28) as a thin compatibility proxy so that
existing imports `from application.interfaces.ports import X` continue to work
without runtime warnings.

Contents:
- Legacy sync Protocols (UnitOfWork, *Repository) are kept for backward compatibility
  for sync use cases and in-memory adapters.
- Async Protocols are NOT defined here; they are re-exported from application.ports.

Future cleanup iteration will remove this file after downstream migration.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Protocol, runtime_checkable

from py_accountant.application.dto.models import (
    AccountDTO,
    CurrencyDTO,
    ExchangeRateEventDTO,
    RichTransactionDTO,
    TransactionDTO,
)

# ================ Legacy sync Protocols (DEPRECATED surface) ================


@runtime_checkable
class ExchangeRateEventsRepository(Protocol):
    """События изменения курсов (sync) + TTL/архив (CRUD + primitives)."""

    def add_event(self, code: str, rate: Decimal, occurred_at: datetime, policy_applied: str, source: str | None) -> ExchangeRateEventDTO: ...
    def list_events(self, code: str | None = None, limit: int | None = None) -> list[ExchangeRateEventDTO]: ...
    def list_old_events(self, cutoff: datetime, limit: int) -> list[ExchangeRateEventDTO]: ...
    def delete_events_by_ids(self, ids: list[int]) -> int: ...
    def archive_events(self, rows: list[ExchangeRateEventDTO], archived_at: datetime) -> int: ...


@runtime_checkable
class UnitOfWork(Protocol):
    """Транзакционная граница приложения (sync)."""

    @property
    def accounts(self) -> AccountRepository: ...

    @property
    def currencies(self) -> CurrencyRepository: ...

    @property
    def transactions(self) -> TransactionRepository: ...

    # Removed: balances repository

    @property
    def exchange_rate_events(self) -> ExchangeRateEventsRepository: ...  # type: ignore[override]

    def commit(self) -> None: ...
    def rollback(self) -> None: ...


@runtime_checkable
class CurrencyRepository(Protocol):
    def get_by_code(self, code: str) -> CurrencyDTO | None: ...
    def upsert(self, dto: CurrencyDTO) -> CurrencyDTO: ...
    def list_all(self) -> list[CurrencyDTO]: ...
    def get_base(self) -> CurrencyDTO | None: ...
    def set_base(self, code: str) -> None: ...
    def clear_base(self) -> None: ...
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


# ================ Async Protocol re-exports (preferred surface) ================

from py_accountant.application.ports import (  # noqa: E402,F401
    AsyncAccountRepository,
    AsyncCurrencyRepository,
    AsyncExchangeRateEventsRepository,
    AsyncTransactionRepository,
    AsyncUnitOfWork,
    Clock,
    SupportsCommitRollback,
)

__all__ = [
    # sync legacy
    "Clock",
    "UnitOfWork",
    "CurrencyRepository",
    "AccountRepository",
    "TransactionRepository",
    "ExchangeRateEventsRepository",
    # async preferred
    "SupportsCommitRollback",
    "AsyncCurrencyRepository",
    "AsyncAccountRepository",
    "AsyncTransactionRepository",
    "AsyncExchangeRateEventsRepository",
    "AsyncUnitOfWork",
]
