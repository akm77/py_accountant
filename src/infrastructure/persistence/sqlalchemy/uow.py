from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.orm import Session

from application.interfaces.ports import (
    AccountRepository,
    BalanceRepository,
    CurrencyRepository,
    ExchangeRateEventsRepository,
    TransactionRepository,
    UnitOfWork,
)
from infrastructure.persistence.sqlalchemy.async_engine import (
    get_async_engine,
    get_async_session_factory,
)
from infrastructure.persistence.sqlalchemy.models import make_session_factory
from infrastructure.persistence.sqlalchemy.repositories import (
    SqlAlchemyAccountRepository,
    SqlAlchemyBalanceRepository,
    SqlAlchemyCurrencyRepository,
    SqlAlchemyExchangeRateEventsRepository,
    SqlAlchemyTransactionRepository,
)
from infrastructure.persistence.sqlalchemy.repositories_async import (
    AsyncSqlAlchemyAccountRepository,
    AsyncSqlAlchemyBalanceRepository,
    AsyncSqlAlchemyCurrencyRepository,
    AsyncSqlAlchemyExchangeRateEventsRepository,
    AsyncSqlAlchemyTransactionRepository,
)

logger = logging.getLogger(__name__)


@dataclass
class SqlAlchemyUnitOfWork(UnitOfWork):  # type: ignore[misc]
    """Synchronous SQLAlchemy Unit of Work.

    This is the existing sync UoW used throughout the app and tests. It remains
    unchanged in ASYNC-02 to avoid breaking callers. Async UoW is introduced
    alongside as a separate class.
    """

    session_factory: Callable[[], Session]

    def __init__(self, url: str | None = None) -> None:
        """Initialize UoW with a synchronous Session factory.

        Parameters:
        - url: Optional SQLAlchemy URL. Defaults to in-memory SQLite if not provided.
        """
        self.session_factory = make_session_factory(url)
        self._session: Session | None = None
        self._accounts: AccountRepository | None = None
        self._currencies: CurrencyRepository | None = None
        self._transactions: TransactionRepository | None = None
        self._balances: BalanceRepository | None = None
        self._rate_events: ExchangeRateEventsRepository | None = None

    def _ensure_session(self) -> Session:
        """Lazily create and return the underlying sync Session."""
        if self._session is None:
            self._session = self.session_factory()
        return self._session

    @property
    def accounts(self) -> AccountRepository:
        """Return AccountRepository bound to the current Session."""
        if not self._accounts:
            self._accounts = SqlAlchemyAccountRepository(self._ensure_session())
        return self._accounts

    @property
    def currencies(self) -> CurrencyRepository:
        """Return CurrencyRepository bound to the current Session."""
        if not self._currencies:
            self._currencies = SqlAlchemyCurrencyRepository(self._ensure_session())
        return self._currencies

    @property
    def transactions(self) -> TransactionRepository:
        """Return TransactionRepository bound to the current Session."""
        if not self._transactions:
            self._transactions = SqlAlchemyTransactionRepository(self._ensure_session())
        return self._transactions

    @property
    def balances(self) -> BalanceRepository:
        """Return BalanceRepository bound to the current Session."""
        if not self._balances:
            self._balances = SqlAlchemyBalanceRepository(self._ensure_session())
        return self._balances

    @property
    def exchange_rate_events(self) -> ExchangeRateEventsRepository:  # type: ignore[override]
        """Return ExchangeRateEventsRepository bound to the current Session."""
        if not self._rate_events:
            self._rate_events = SqlAlchemyExchangeRateEventsRepository(self._ensure_session())
        return self._rate_events

    def commit(self) -> None:
        """Commit the current transaction if a Session exists."""
        if self._session:
            self._session.commit()

    def rollback(self) -> None:
        """Rollback the current transaction if a Session exists."""
        if self._session:
            self._session.rollback()

    def close(self) -> None:
        """Close the current Session if it exists."""
        if self._session:
            self._session.close()
            self._session = None


class AsyncSqlAlchemyUnitOfWork:
    """Asynchronous SQLAlchemy Unit of Work (async context manager).

    Provides transactional boundary using ``AsyncSession``. Designed to coexist
    with the legacy synchronous UoW until repositories are migrated in ASYNC-03.

    Usage:
        async with AsyncSqlAlchemyUnitOfWork(url) as uow:
            await uow.session.execute(text("..."))
            # On successful exit -> COMMIT, on exception -> ROLLBACK

    Notes:
    - Repository properties are now provided (ASYNC-03) and return async
      repository instances lazily, bound to the current ``AsyncSession``. The
      names mirror the sync UoW for familiarity, but they expose async
      repositories and are intended to be used from async code only.
    """

    def __init__(self, url: str | None = None, *, echo: bool = False) -> None:
        """Create Async UoW with its own engine and async session factory.

        Parameters:
        - url: Database URL (sync or async). Defaults to an in-memory SQLite if None.
        - echo: Enable SQLAlchemy echo for debugging.
        """
        self._url = url or "sqlite+aiosqlite:///:memory:"
        self._engine: AsyncEngine = get_async_engine(self._url, echo=echo)
        self._session_factory = get_async_session_factory(self._engine)
        self._session: AsyncSession | None = None
        self._entered: bool = False
        # Lazy async repositories
        self._a_accounts: AsyncSqlAlchemyAccountRepository | None = None
        self._a_currencies: AsyncSqlAlchemyCurrencyRepository | None = None
        self._a_transactions: AsyncSqlAlchemyTransactionRepository | None = None
        self._a_balances: AsyncSqlAlchemyBalanceRepository | None = None
        self._a_rate_events: AsyncSqlAlchemyExchangeRateEventsRepository | None = None

    @property
    def engine(self) -> AsyncEngine:
        """Return the internal ``AsyncEngine`` (primarily for tests/schema setup)."""
        return self._engine

    @property
    def session(self) -> AsyncSession:
        """Return the active AsyncSession.

        Raises:
        - RuntimeError: if accessed outside of an active context manager.
        """
        if not self._session:
            raise RuntimeError("AsyncSqlAlchemyUnitOfWork.session is only available inside 'async with' block")
        return self._session

    @property
    def session_factory(self):
        """Return the internal async session factory (testing/helper use)."""
        return self._session_factory

    async def __aenter__(self) -> AsyncSqlAlchemyUnitOfWork:
        """Enter async context: open AsyncSession and begin a transaction."""
        if self._entered:
            raise RuntimeError("AsyncSqlAlchemyUnitOfWork instance cannot be re-entered")
        self._entered = True
        logger.debug("AsyncUoW: opening session and beginning transaction")
        self._session = self._session_factory()
        # Explicit transaction begin to enforce rollback on exceptions
        await self._session.begin()
        # Reset repositories cache on fresh session
        self._a_accounts = None
        self._a_currencies = None
        self._a_transactions = None
        self._a_balances = None
        self._a_rate_events = None
        return self

    async def __aexit__(self, exc_type, exc: BaseException | None, tb: Any) -> None:  # noqa: D401
        """Exit async context: commit on success, rollback on error; always close session."""
        try:
            if not self._session:
                logger.warning("AsyncUoW.__aexit__ called without an active session; no-op")
                return None
            if exc is None:
                logger.debug("AsyncUoW: committing transaction")
                try:
                    await self._session.commit()
                except Exception:
                    logger.exception("AsyncUoW: commit failed; attempting rollback")
                    try:
                        await self._session.rollback()
                    except Exception:
                        logger.exception("AsyncUoW: rollback after commit failure also failed")
                    raise
            else:
                logger.debug("AsyncUoW: exception detected -> rollback", exc_info=exc)
                try:
                    await self._session.rollback()
                except Exception:
                    logger.exception("AsyncUoW: rollback failed during exception handling")
                    # Don't suppress original exception
        finally:
            if self._session is not None:
                try:
                    await self._session.close()
                except Exception:
                    logger.exception("AsyncUoW: session.close() failed")
                finally:
                    self._session = None
                    self._entered = False
                    # Drop repositories cache along with the session
                    self._a_accounts = None
                    self._a_currencies = None
                    self._a_transactions = None
                    self._a_balances = None
                    self._a_rate_events = None

    async def commit(self) -> None:
        """Explicitly commit the current transaction if a session is active."""
        if not self._session:
            logger.warning("AsyncUoW.commit() called without an active session; no-op")
            return None
        await self._session.commit()

    async def rollback(self) -> None:
        """Explicitly rollback the current transaction if a session is active."""
        if not self._session:
            logger.warning("AsyncUoW.rollback() called without an active session; no-op")
            return None
        await self._session.rollback()

    def close(self) -> None:
        """Synchronously close the session if active.

        Prefer using the async context manager. This helper attempts to close
        without requiring an event loop by calling ``sync_session.close()``.
        """
        if not self._session:
            return None
        try:
            # Close via underlying sync session to avoid event loop requirements
            self._session.sync_session.close()
        except Exception:
            logger.exception("AsyncUoW.close(): sync close failed; attempting async close via asyncio.run")
            try:
                # This will fail if we're already inside a running loop
                asyncio.run(self._session.close())
            except RuntimeError:
                logger.warning("AsyncUoW.close(): cannot run event loop; session may remain open")
        finally:
            self._session = None
            self._entered = False
            self._a_accounts = None
            self._a_currencies = None
            self._a_transactions = None
            self._a_balances = None
            self._a_rate_events = None

    # Async repositories (lazy properties)
    @property
    def accounts(self) -> AsyncSqlAlchemyAccountRepository:
        """Return async ``Account`` repository bound to the current session.

        Note: name mirrors the sync UoW for familiarity. This returns an async
        repository and should be used only from async code.
        """
        if not self._session:
            raise RuntimeError("AsyncSqlAlchemyUnitOfWork.accounts requires an active session")
        if not self._a_accounts:
            self._a_accounts = AsyncSqlAlchemyAccountRepository(self._session)
        return self._a_accounts

    @property
    def currencies(self) -> AsyncSqlAlchemyCurrencyRepository:
        """Return async ``Currency`` repository bound to the current session."""
        if not self._session:
            raise RuntimeError("AsyncSqlAlchemyUnitOfWork.currencies requires an active session")
        if not self._a_currencies:
            self._a_currencies = AsyncSqlAlchemyCurrencyRepository(self._session)
        return self._a_currencies

    @property
    def transactions(self) -> AsyncSqlAlchemyTransactionRepository:
        """Return async ``Transaction`` repository bound to the current session."""
        if not self._session:
            raise RuntimeError("AsyncSqlAlchemyUnitOfWork.transactions requires an active session")
        if not self._a_transactions:
            self._a_transactions = AsyncSqlAlchemyTransactionRepository(self._session)
        return self._a_transactions

    @property
    def balances(self) -> AsyncSqlAlchemyBalanceRepository:
        """Return async ``Balance`` repository bound to the current session."""
        if not self._session:
            raise RuntimeError("AsyncSqlAlchemyUnitOfWork.balances requires an active session")
        if not self._a_balances:
            self._a_balances = AsyncSqlAlchemyBalanceRepository(self._session)
        return self._a_balances

    @property
    def exchange_rate_events(self) -> AsyncSqlAlchemyExchangeRateEventsRepository:  # type: ignore[override]
        """Return async FX audit repository bound to the current session."""
        if not self._session:
            raise RuntimeError("AsyncSqlAlchemyUnitOfWork.exchange_rate_events requires an active session")
        if not self._a_rate_events:
            self._a_rate_events = AsyncSqlAlchemyExchangeRateEventsRepository(self._session)
        return self._a_rate_events


class SyncUnitOfWorkWrapper:
    """Synchronous wrapper over ``AsyncSqlAlchemyUnitOfWork``.

    Provides a blocking context manager that internally drives the async UoW
    using ``asyncio.run`` when no event loop is running. If an event loop is
    already running, a clear ``RuntimeError`` is raised to avoid nested loops.

    This is intended as a compatibility bridge for synchronous code paths (CLI
    and legacy tests) that need to call commit/rollback on an async UoW.
    """

    def __init__(self, async_uow: AsyncSqlAlchemyUnitOfWork) -> None:
        """Initialize the wrapper with an async UoW instance."""
        self._uow = async_uow

    @staticmethod
    def _ensure_no_running_loop() -> None:
        """Raise RuntimeError if called from within an active event loop."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return  # No running loop -> OK
        raise RuntimeError(
            "SyncUnitOfWorkWrapper cannot be used inside an active event loop. "
            "Use the async UoW directly or schedule operations properly."
        )

    def __enter__(self) -> SyncUnitOfWorkWrapper:
        """Enter blocking context by awaiting async UoW.__aenter__ via asyncio.run."""
        self._ensure_no_running_loop()
        asyncio.run(self._uow.__aenter__())
        return self

    def __exit__(self, exc_type, exc: BaseException | None, tb: Any) -> None:
        """Exit blocking context by awaiting async UoW.__aexit__ via asyncio.run."""
        self._ensure_no_running_loop()
        asyncio.run(self._uow.__aexit__(exc_type, exc, tb))

    def commit(self) -> None:
        """Synchronously commit by awaiting async commit via asyncio.run."""
        self._ensure_no_running_loop()
        asyncio.run(self._uow.commit())

    def rollback(self) -> None:
        """Synchronously rollback by awaiting async rollback via asyncio.run."""
        self._ensure_no_running_loop()
        asyncio.run(self._uow.rollback())

    def close(self) -> None:
        """Close underlying UoW session, if any, using its sync helper."""
        self._uow.close()
