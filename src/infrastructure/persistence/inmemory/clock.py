from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from application.interfaces.ports import (
    AccountRepository,
    Clock,
    CurrencyRepository,
    TransactionRepository,
    UnitOfWork,
)
from infrastructure.persistence.inmemory.repositories import (
    InMemoryAccountRepository,
    InMemoryCurrencyRepository,
    InMemoryTransactionRepository,
)


class SystemClock(Clock):  # type: ignore[misc]
    def now(self) -> datetime:  # noqa: D401
        return datetime.now(UTC)




class FixedClock(Clock):  # type: ignore[misc]
    def __init__(self, fixed: datetime) -> None:
        self._fixed = fixed

    def now(self) -> datetime:  # noqa: D401
        return self._fixed



@dataclass
class InMemoryUnitOfWork(UnitOfWork):  # type: ignore[misc]
    accounts_repo: InMemoryAccountRepository = InMemoryAccountRepository()
    currencies_repo: InMemoryCurrencyRepository = InMemoryCurrencyRepository()
    transactions_repo: InMemoryTransactionRepository = InMemoryTransactionRepository()

    @property
    def accounts(self) -> AccountRepository:  # noqa: D401
        return self.accounts_repo

    @property
    def currencies(self) -> CurrencyRepository:  # noqa: D401
        return self.currencies_repo

    @property
    def transactions(self) -> TransactionRepository:  # noqa: D401
        return self.transactions_repo

    def commit(self) -> None:  # noqa: D401
        # No-op for in-memory
        return None

    def rollback(self) -> None:  # noqa: D401
        # No-op for in-memory
        return None

