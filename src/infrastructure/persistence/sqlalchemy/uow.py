from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from application.interfaces.ports import (
    AccountRepository,
    CurrencyRepository,
    TransactionRepository,
    UnitOfWork,
    BalanceRepository,
)
from infrastructure.persistence.sqlalchemy.models import make_session_factory
from infrastructure.persistence.sqlalchemy.repositories import (
    SqlAlchemyAccountRepository,
    SqlAlchemyBalanceRepository,
    SqlAlchemyCurrencyRepository,
    SqlAlchemyTransactionRepository,
)


@dataclass
class SqlAlchemyUnitOfWork(UnitOfWork):  # type: ignore[misc]
    session_factory: callable

    def __init__(self, url: str | None = None) -> None:  # noqa: D401
        self.session_factory = make_session_factory(url)
        self._session: Session | None = None
        self._accounts: AccountRepository | None = None
        self._currencies: CurrencyRepository | None = None
        self._transactions: TransactionRepository | None = None
        self._balances: BalanceRepository | None = None

    def _ensure_session(self) -> Session:
        if self._session is None:
            self._session = self.session_factory()
        return self._session

    @property
    def accounts(self) -> AccountRepository:  # noqa: D401
        if not self._accounts:
            self._accounts = SqlAlchemyAccountRepository(self._ensure_session())
        return self._accounts

    @property
    def currencies(self) -> CurrencyRepository:  # noqa: D401
        if not self._currencies:
            self._currencies = SqlAlchemyCurrencyRepository(self._ensure_session())
        return self._currencies

    @property
    def transactions(self) -> TransactionRepository:  # noqa: D401
        if not self._transactions:
            self._transactions = SqlAlchemyTransactionRepository(self._ensure_session())
        return self._transactions

    @property
    def balances(self) -> BalanceRepository:  # noqa: D401
        if not self._balances:
            self._balances = SqlAlchemyBalanceRepository(self._ensure_session())
        return self._balances

    def commit(self) -> None:  # noqa: D401
        if self._session:
            self._session.commit()

    def rollback(self) -> None:  # noqa: D401
        if self._session:
            self._session.rollback()

    def close(self) -> None:  # noqa: D401
        if self._session:
            self._session.close()
            self._session = None
