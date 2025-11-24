"""UnitOfWork factory for telegram bot."""
from __future__ import annotations

from typing import Callable

from py_accountant.application.ports import AsyncUnitOfWork
from py_accountant.infrastructure.persistence.sqlalchemy.uow import AsyncSqlAlchemyUnitOfWork

from config import settings


def create_uow_factory() -> Callable[[], AsyncUnitOfWork]:
    """Create UoW factory for dependency injection.

    Returns:
        Factory function that creates new UoW instances.

    Notes:
        Each invocation of the factory returns a NEW UoW instance.
        This is correct behavior - one UoW per request/command.

    Example:
        >>> uow_factory = create_uow_factory()
        >>> async with uow_factory() as uow:
        ...     # Use uow.accounts, uow.currencies, etc.
        ...     await uow.commit()
    """

    def factory() -> AsyncUnitOfWork:
        return AsyncSqlAlchemyUnitOfWork(
            url=settings.pyacc_database_url_async,
            echo=False,  # Disable SQL echo in production
        )

    return factory

