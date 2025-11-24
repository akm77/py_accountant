from __future__ import annotations

import asyncio
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from py_accountant.infrastructure.persistence.sqlalchemy.async_engine import (
    get_async_engine,
    get_async_session_factory,
)
from py_accountant.infrastructure.persistence.sqlalchemy.repositories_async import (
    AsyncSqlAlchemyAccountRepository,
    AsyncSqlAlchemyCurrencyRepository,
    AsyncSqlAlchemyExchangeRateEventsRepository,
    AsyncSqlAlchemyTransactionRepository,
)

logger = logging.getLogger(__name__)


class AsyncSqlAlchemyUnitOfWork:
    """Minimal async SQLAlchemy Unit of Work (legacy sync слой удалён в I29).

    Responsibilities:
    - Manage a single AsyncSession per context (open, begin, commit/rollback, close).
    - Expose lazy repositories bound to the current session.
    """

    def __init__(self, url: str | None = None, *, echo: bool = False) -> None:
        """Initialize with its own engine and session factory.

        Args:
        - url: database URL (defaults to in-memory SQLite if None).
        - echo: enable SQLAlchemy echo for debugging.
        """
        self._url = url or "sqlite+aiosqlite:///:memory:"
        self._engine: AsyncEngine = get_async_engine(self._url, echo=echo)
        self._session_factory = get_async_session_factory(self._engine)
        self._session: AsyncSession | None = None
        self._entered: bool = False
        self._explicit_commit: bool = False
        # Lazy async repositories
        self._a_accounts: AsyncSqlAlchemyAccountRepository | None = None
        self._a_currencies: AsyncSqlAlchemyCurrencyRepository | None = None
        self._a_transactions: AsyncSqlAlchemyTransactionRepository | None = None
        self._a_rate_events: AsyncSqlAlchemyExchangeRateEventsRepository | None = None

    @property
    def engine(self) -> AsyncEngine:
        """Return the internal AsyncEngine (useful for migrations/tests)."""
        return self._engine

    @property
    def session(self) -> AsyncSession:
        """Return the active AsyncSession; only valid inside an 'async with' block.

        Raises:
        - RuntimeError: if accessed outside of an active context.
        """
        if not self._session:
            raise RuntimeError(
                "AsyncSqlAlchemyUnitOfWork.session is only available inside 'async with' block"
            )
        return self._session

    @property
    def session_factory(self):
        """Return the internal async session factory (primarily for tests/utilities)."""
        return self._session_factory

    async def __aenter__(self) -> AsyncSqlAlchemyUnitOfWork:
        """Open a new AsyncSession and begin a transaction.

        Resets lazy repositories for this context.
        """
        if self._entered:
            raise RuntimeError("AsyncSqlAlchemyUnitOfWork instance cannot be re-entered")
        self._entered = True
        self._explicit_commit = False
        logger.debug("AsyncUoW: opening session and beginning transaction")
        self._session = self._session_factory()
        await self._session.begin()
        # Reset repositories cache on fresh session
        self._a_accounts = None
        self._a_currencies = None
        self._a_transactions = None
        self._a_rate_events = None
        return self

    async def __aexit__(self, exc_type, exc: BaseException | None, tb: Any) -> None:
        """Finalize the context: rollback on error; otherwise commit if not explicit.

        Always closes the session and clears cached repositories.
        """
        try:
            if not self._session:
                logger.debug("AsyncUoW.__aexit__: no active session; nothing to finalize")
                return None
            if exc is not None:
                logger.debug("AsyncUoW: exception detected -> rollback", exc_info=exc)
                try:
                    await self._session.rollback()
                except Exception:
                    logger.exception("AsyncUoW: rollback failed during exception handling")
            else:
                if not self._explicit_commit:
                    logger.debug("AsyncUoW: committing transaction on exit")
                    try:
                        await self._session.commit()
                    except Exception:
                        logger.exception("AsyncUoW: commit on exit failed; attempting rollback")
                        try:
                            await self._session.rollback()
                        except Exception:
                            logger.exception("AsyncUoW: rollback after exit-commit failure also failed")
                        raise
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
                    self._a_rate_events = None

    async def commit(self) -> None:
        """Commit the current transaction if a session is active.

        Marks this context as having performed an explicit commit.
        """
        if not self._session:
            raise RuntimeError("AsyncSqlAlchemyUnitOfWork.commit() requires an active session")
        await self._session.commit()
        self._explicit_commit = True

    async def rollback(self) -> None:
        """Rollback the current transaction if a session is active."""
        if not self._session:
            raise RuntimeError("AsyncSqlAlchemyUnitOfWork.rollback() requires an active session")
        await self._session.rollback()

    def close(self) -> None:
        """Best-effort synchronous close for cases without an event loop.

        Prefer using the async context manager in application code.
        """
        if not self._session:
            return None
        try:
            self._session.sync_session.close()
        except Exception:
            logger.exception("AsyncUoW.close(): sync close failed; attempting async close via asyncio.run")
            try:
                asyncio.run(self._session.close())
            except RuntimeError:
                logger.warning("AsyncUoW.close(): cannot run event loop; session may remain open")
        finally:
            self._session = None
            self._entered = False
            self._a_accounts = None
            self._a_currencies = None
            self._a_transactions = None
            self._a_rate_events = None

    # Async repositories (lazy properties)
    @property
    def accounts(self) -> AsyncSqlAlchemyAccountRepository:
        """Return async Account repository bound to the current session."""
        if not self._session:
            raise RuntimeError("AsyncSqlAlchemyUnitOfWork.accounts requires an active session")
        if not self._a_accounts:
            self._a_accounts = AsyncSqlAlchemyAccountRepository(self._session)
        return self._a_accounts

    @property
    def currencies(self) -> AsyncSqlAlchemyCurrencyRepository:
        """Return async Currency repository bound to the current session."""
        if not self._session:
            raise RuntimeError("AsyncSqlAlchemyUnitOfWork.currencies requires an active session")
        if not self._a_currencies:
            self._a_currencies = AsyncSqlAlchemyCurrencyRepository(self._session)
        return self._a_currencies

    @property
    def transactions(self) -> AsyncSqlAlchemyTransactionRepository:
        """Return async Transaction repository bound to the current session."""
        if not self._session:
            raise RuntimeError("AsyncSqlAlchemyUnitOfWork.transactions requires an active session")
        if not self._a_transactions:
            self._a_transactions = AsyncSqlAlchemyTransactionRepository(self._session)
        return self._a_transactions


    @property
    def exchange_rate_events(self) -> AsyncSqlAlchemyExchangeRateEventsRepository:  # type: ignore[override]
        """Return async ExchangeRateEvents repository bound to the current session."""
        if not self._session:
            raise RuntimeError(
                "AsyncSqlAlchemyUnitOfWork.exchange_rate_events requires an active session"
            )
        if not self._a_rate_events:
            self._a_rate_events = AsyncSqlAlchemyExchangeRateEventsRepository(self._session)
        return self._a_rate_events
