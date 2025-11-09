from __future__ import annotations

from dataclasses import dataclass, field

from application.interfaces.ports import (
    AccountRepository,
    BalanceRepository,
    CurrencyRepository,
    TransactionRepository,
    UnitOfWork,
)
from infrastructure.persistence.inmemory.repositories import (
    InMemoryAccountRepository,
    InMemoryCurrencyRepository,
    InMemoryTransactionRepository,
)


@dataclass
class InMemoryUnitOfWork(UnitOfWork):  # type: ignore[misc]
    accounts_repo: InMemoryAccountRepository = field(default_factory=InMemoryAccountRepository)
    currencies_repo: InMemoryCurrencyRepository = field(default_factory=InMemoryCurrencyRepository)
    transactions_repo: InMemoryTransactionRepository = field(default_factory=InMemoryTransactionRepository)

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
    def balances(self) -> BalanceRepository:  # type: ignore[override]
        raise NotImplementedError("In-memory UoW has no BalanceRepository")

    def commit(self) -> None:  # noqa: D401
        return None

    def rollback(self) -> None:  # noqa: D401
        return None
