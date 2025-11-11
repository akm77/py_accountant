from __future__ import annotations

import asyncio
import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from infrastructure.config.settings import get_settings
from infrastructure.persistence.sqlalchemy.async_engine import (
    get_async_engine,
    get_async_session_factory,
)
from infrastructure.persistence.sqlalchemy.repositories_async import (
    AsyncSqlAlchemyAccountRepository,
    AsyncSqlAlchemyBalanceRepository,
    AsyncSqlAlchemyCurrencyRepository,
    AsyncSqlAlchemyExchangeRateEventsRepository,
    AsyncSqlAlchemyTransactionRepository,
)

logger = logging.getLogger(__name__)


class AsyncSqlAlchemyUnitOfWork:
    """Asynchronous SQLAlchemy Unit of Work (async context manager).

    Provides transactional boundary using ``AsyncSession``. Designed as the
    sole runtime UoW (ASYNC-10), with sync access exposed only via
    presentation/async_bridge facades.

    Behavior (ASYNC-09 additions, kept intact):
    - On enter: begin transaction and, for PostgreSQL, optionally set
      ``SET LOCAL statement_timeout = :ms`` when configured (no-op for SQLite/others).
    - On commit: retry limited times on transient DB errors (serialization
      failure, deadlock, or connection-invalidated OperationalError/DBAPIError)
      with exponential backoff. Non-transient errors are not retried.
    """

    def __init__(self, url: str | None = None, *, echo: bool = False) -> None:
        """Create Async UoW with its own engine and async session factory.

        Parameters:
        - url: Database URL (async driver recommended). Defaults to an in-memory SQLite if None.
        - echo: Enable SQLAlchemy echo for debugging.
        """
        self._url = url or "sqlite+aiosqlite:///:memory:"
        self._engine: AsyncEngine = get_async_engine(self._url, echo=echo)
        self._session_factory = get_async_session_factory(self._engine)
        self._session: AsyncSession | None = None
        self._entered: bool = False
        self._committed: bool = False
        self._commit_attempted: bool = False
        # Lazy async repositories
        self._a_accounts: AsyncSqlAlchemyAccountRepository | None = None
        self._a_currencies: AsyncSqlAlchemyCurrencyRepository | None = None
        self._a_transactions: AsyncSqlAlchemyTransactionRepository | None = None
        self._a_balances: AsyncSqlAlchemyBalanceRepository | None = None
        self._a_rate_events: AsyncSqlAlchemyExchangeRateEventsRepository | None = None
        # Cached settings snapshot for retries/timeout
        self._settings = get_settings()

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
        """Enter async context: open AsyncSession and begin a transaction.

        Additionally, for PostgreSQL and when ``DB_STATEMENT_TIMEOUT`` is set
        to a positive value, execute ``SET LOCAL statement_timeout`` scoped to
        the transaction. This is a safe no-op for other dialects.
        """
        if self._entered:
            raise RuntimeError("AsyncSqlAlchemyUnitOfWork instance cannot be re-entered")
        self._entered = True
        self._committed = False
        self._commit_attempted = False
        logger.debug("AsyncUoW: opening session and beginning transaction")
        self._session = self._session_factory()
        # Explicit transaction begin to enforce rollback on exceptions
        await self._session.begin()
        # Apply Postgres statement timeout if configured
        try:
            dialect_name = getattr(self._engine.dialect, "name", "")
            timeout_ms = int(getattr(self._settings, "db_statement_timeout_ms", 0))
            if timeout_ms > 0 and str(dialect_name).startswith("postgresql"):
                logger.debug("AsyncUoW: applying SET LOCAL statement_timeout=%s ms", timeout_ms)
                await self._session.execute(text("SET LOCAL statement_timeout = :ms"), {"ms": timeout_ms})
        except Exception:
            # Defensive: do not break entry if timeout set fails
            logger.exception("AsyncUoW: failed to apply statement_timeout; proceeding without it")
        # Reset repositories cache on fresh session
        self._a_accounts = None
        self._a_currencies = None
        self._a_transactions = None
        self._a_balances = None
        self._a_rate_events = None
        return self

    @staticmethod
    def _is_transient_error(exc: BaseException) -> bool:
        """Return True if the DB error is considered transient and safe to retry.

        Checks:
        - DBAPIError with connection_invalidated True
        - SQLSTATE codes for serialization failure (40001) and deadlock (40P01)
        - OperationalError that likely indicates a transient connection issue
        """
        # SQLSTATE extraction helper
        def _sqlstate(err: Any) -> str | None:
            code = None
            orig = getattr(err, "orig", None)
            if orig is None:
                return None
            # asyncpg exceptions usually expose .sqlstate
            code = getattr(orig, "sqlstate", None)
            if code:
                return str(code)
            # psycopg style
            code = getattr(orig, "pgcode", None)
            if code:
                return str(code)
            # Some drivers put it in args/messages; best-effort skip
            return None

        if isinstance(exc, DBAPIError):
            if getattr(exc, "connection_invalidated", False):
                return True
            code = _sqlstate(exc)
            if code in {"40001", "40P01"}:
                return True
        if isinstance(exc, OperationalError):
            # OperationalError can be transient (disconnects, timeouts)
            # Without SQLSTATE, err on the safe side only if connection invalidated
            if getattr(exc, "connection_invalidated", False):
                return True
            code = _sqlstate(exc)
            if code in {"40001", "40P01"}:
                return True
        return False

    async def _commit_with_retry(self) -> None:
        """Commit current transaction with bounded retries on transient errors.

        Backoff parameters are read from settings: attempts, base backoff, max cap.
        On each transient failure, perform rollback and sleep before retrying.
        Non-transient errors are re-raised immediately.
        """
        if not self._session:
            logger.warning("AsyncUoW.commit() called without an active session; no-op")
            return None
        self._commit_attempted = True
        attempts = max(1, int(getattr(self._settings, "db_retry_attempts", 3)))
        backoff_ms = max(1, int(getattr(self._settings, "db_retry_backoff_ms", 50)))
        max_backoff_ms = max(backoff_ms, int(getattr(self._settings, "db_retry_max_backoff_ms", 1000)))
        last_exc: BaseException | None = None
        for attempt in range(1, attempts + 1):
            try:
                await self._session.commit()
                self._committed = True
                return None
            except (DBAPIError, OperationalError) as exc:  # type: ignore[misc]
                # Decide on retry
                if not self._is_transient_error(exc) or attempt == attempts:
                    last_exc = exc
                    break
                # rollback before retrying commit
                try:
                    await self._session.rollback()
                except Exception:
                    logger.exception("AsyncUoW: rollback after transient commit failure also failed")
                delay_ms = min(max_backoff_ms, backoff_ms * (2 ** (attempt - 1)))
                sqlstate = getattr(getattr(exc, "orig", None), "sqlstate", None) or getattr(
                    getattr(exc, "orig", None), "pgcode", None
                )
                logger.warning(
                    "AsyncUoW: transient commit failure (attempt %s/%s, sqlstate=%s): %s; retrying in %sms",
                    attempt,
                    attempts,
                    sqlstate,
                    type(exc).__name__,
                    delay_ms,
                )
                await asyncio.sleep(delay_ms / 1000.0)
            except Exception:
                # Non-DB error -> don't retry
                raise
        # Exhausted or non-retryable
        assert last_exc is not None
        raise last_exc

    async def __aexit__(self, exc_type, exc: BaseException | None, tb: Any) -> None:  # noqa: D401
        """Exit async context with safe finalization.

        Rules:
        - If an exception occurred inside the block -> rollback.
        - If no exception and commit previously succeeded -> no-op (already committed).
        - If no exception and commit was attempted but failed -> rollback to avoid partial state; don't re-raise here.
        - If no exception and no commit attempted -> perform commit with retry once.
        Always close the session.
        """
        try:
            if not self._session:
                logger.warning("AsyncUoW.__aexit__ called without an active session; no-op")
                return None
            if exc is not None:
                logger.debug("AsyncUoW: exception detected -> rollback", exc_info=exc)
                try:
                    await self._session.rollback()
                except Exception:
                    logger.exception("AsyncUoW: rollback failed during exception handling")
            else:
                if self._committed:
                    # Already committed explicitly inside the context
                    pass
                elif self._commit_attempted and not self._committed:
                    # Commit was attempted and failed earlier -> rollback to clean up
                    logger.debug("AsyncUoW: prior commit attempt failed -> rollback on exit")
                    try:
                        await self._session.rollback()
                    except Exception:
                        logger.exception("AsyncUoW: rollback after failed commit attempt also failed")
                else:
                    logger.debug("AsyncUoW: committing transaction on exit")
                    try:
                        await self._commit_with_retry()
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
                    self._committed = False
                    self._commit_attempted = False
                    # Drop repositories cache along with the session
                    self._a_accounts = None
                    self._a_currencies = None
                    self._a_transactions = None
                    self._a_balances = None
                    self._a_rate_events = None

    async def commit(self) -> None:
        """Explicitly commit the current transaction if a session is active (with retries)."""
        if not self._session:
            logger.warning("AsyncUoW.commit() called without an active session; no-op")
            return None
        await self._commit_with_retry()

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

