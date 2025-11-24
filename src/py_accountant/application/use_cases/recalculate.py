from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from py_accountant.application.ports import Clock
from py_accountant.application.ports import SupportsCommitRollback as UnitOfWork
from py_accountant.domain import AccountBalanceServiceProtocol, InMemoryAccountBalanceService


@dataclass
class RecalculateAccountBalance:
    """Force balance recomputation for an account up to as_of.

    Contract:
    - If a balance service is provided (in-memory or SQL), call get_balance(recompute=True)
      to update cache transactionally and return the amount.
    - If no service is provided, fall back to a direct repository aggregation.
    """

    uow: UnitOfWork
    clock: Clock
    balance_service: AccountBalanceServiceProtocol | InMemoryAccountBalanceService | None = None

    def __call__(self, account_full_name: str, as_of: datetime | None = None, force: bool = True) -> Decimal:
        query_time = as_of or self.clock.now()
        if self.balance_service is not None:
            # recompute path ensures cache is refreshed and consistent to query_time
            return self.balance_service.get_balance(account_full_name, query_time, recompute=True)
        # fallback: direct aggregation (no cache layer)
        return self.uow.transactions.account_balance(account_full_name, query_time)
