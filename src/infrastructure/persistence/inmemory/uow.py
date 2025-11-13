from __future__ import annotations

from dataclasses import dataclass, field

from application.interfaces.ports import (
    AccountRepository,
    CurrencyRepository,
    ExchangeRateEventsRepository,
    TransactionRepository,
    UnitOfWork,
)
from infrastructure.persistence.inmemory.repositories import (
    InMemoryAccountRepository,
    InMemoryCurrencyRepository,
    InMemoryExchangeRateEventsRepository,
    InMemoryTransactionRepository,
)


@dataclass
class InMemoryUnitOfWork(UnitOfWork):  # type: ignore[misc]
    accounts_repo: InMemoryAccountRepository = field(default_factory=InMemoryAccountRepository)
    currencies_repo: InMemoryCurrencyRepository = field(default_factory=InMemoryCurrencyRepository)
    transactions_repo: InMemoryTransactionRepository = field(default_factory=InMemoryTransactionRepository)
    rate_events_repo: InMemoryExchangeRateEventsRepository = field(default_factory=InMemoryExchangeRateEventsRepository)

    @property
    def accounts(self) -> AccountRepository:  # noqa: D401
        return self.accounts_repo

    @property
    def currencies(self) -> CurrencyRepository:  # noqa: D401
        return self.currencies_repo

    @property
    def transactions(self) -> TransactionRepository:  # noqa: D401
        return self.transactions_repo

    @property
    def exchange_rate_events(self) -> ExchangeRateEventsRepository:  # type: ignore[override]
        return self.rate_events_repo

    def commit(self) -> None:  # noqa: D401
        return None

    def rollback(self) -> None:  # noqa: D401
        return None
