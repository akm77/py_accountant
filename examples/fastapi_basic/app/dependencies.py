"""Dependency injection for FastAPI."""
from __future__ import annotations

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from py_accountant.application.use_cases_async.accounts import (
    AsyncCreateAccount,
    AsyncGetAccount,
    AsyncListAccounts,
)
from py_accountant.application.use_cases_async.currencies import (
    AsyncCreateCurrency,
    AsyncGetCurrency,
    AsyncListCurrencies,
)
from py_accountant.application.use_cases_async.ledger import (
    AsyncPostTransaction,
    AsyncGetLedger,
)
from py_accountant.infrastructure.persistence.sqlalchemy.repositories_async import (
    AsyncSqlAlchemyAccountRepository,
    AsyncSqlAlchemyCurrencyRepository,
    AsyncSqlAlchemyLedgerRepository,
)
from py_accountant.infrastructure.persistence.sqlalchemy.uow import AsyncSqlAlchemyUnitOfWork

from .config import settings

# Create async engine at module level
engine = create_async_engine(
    settings.database_url_async,
    echo=settings.debug,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_timeout=settings.db_pool_timeout,
)

# Create session factory
session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency: Get database session.

    Usage:
        @router.get("/example")
        async def example(session: AsyncSession = Depends(get_session)):
            ...
    """
    async with session_factory() as session:
        yield session


async def get_uow() -> AsyncGenerator[AsyncSqlAlchemyUnitOfWork, None]:
    """Dependency: Get Unit of Work.

    Creates a UoW with the session_factory.
    Each request gets a new UoW instance.
    """
    uow = AsyncSqlAlchemyUnitOfWork(session_factory)
    try:
        yield uow
    finally:
        # Cleanup if needed
        pass


# Repository factories
def get_account_repository() -> AsyncSqlAlchemyAccountRepository:
    """Get account repository instance."""
    return AsyncSqlAlchemyAccountRepository()


def get_currency_repository() -> AsyncSqlAlchemyCurrencyRepository:
    """Get currency repository instance."""
    return AsyncSqlAlchemyCurrencyRepository()


def get_ledger_repository() -> AsyncSqlAlchemyLedgerRepository:
    """Get ledger repository instance."""
    return AsyncSqlAlchemyLedgerRepository()


# Use case factories (these will be injected into endpoints)
async def get_create_account_uc(
    uow: AsyncSqlAlchemyUnitOfWork = None,  # Will be injected by FastAPI
) -> AsyncCreateAccount:
    """Factory for AsyncCreateAccount use case."""
    if uow is None:
        async for uow_instance in get_uow():
            uow = uow_instance
            break

    return AsyncCreateAccount(
        account_repo=get_account_repository(),
        currency_repo=get_currency_repository(),
        uow=uow,
    )


async def get_get_account_uc(
    uow: AsyncSqlAlchemyUnitOfWork = None,
) -> AsyncGetAccount:
    """Factory for AsyncGetAccount use case."""
    if uow is None:
        async for uow_instance in get_uow():
            uow = uow_instance
            break

    return AsyncGetAccount(
        account_repo=get_account_repository(),
        uow=uow,
    )


async def get_list_accounts_uc(
    uow: AsyncSqlAlchemyUnitOfWork = None,
) -> AsyncListAccounts:
    """Factory for AsyncListAccounts use case."""
    if uow is None:
        async for uow_instance in get_uow():
            uow = uow_instance
            break

    return AsyncListAccounts(
        account_repo=get_account_repository(),
        uow=uow,
    )


async def get_create_currency_uc(
    uow: AsyncSqlAlchemyUnitOfWork = None,
) -> AsyncCreateCurrency:
    """Factory for AsyncCreateCurrency use case."""
    if uow is None:
        async for uow_instance in get_uow():
            uow = uow_instance
            break

    return AsyncCreateCurrency(
        currency_repo=get_currency_repository(),
        uow=uow,
    )

