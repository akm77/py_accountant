from __future__ import annotations

from abc import abstractmethod
from datetime import datetime
from decimal import Decimal
from typing import Any, Protocol, runtime_checkable

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
    """
    def add_event(self, code: str, rate: Decimal, occurred_at: datetime, policy_applied: str, source: str | None) -> ExchangeRateEventDTO: ...
    def list_events(self, code: str | None = None, limit: int | None = None) -> list[ExchangeRateEventDTO]: ...


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
    def aggregate_trading_balance(self, start: datetime | None, end: datetime | None, base_currency: str | None = None) -> TradingBalanceDTO: ...
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
