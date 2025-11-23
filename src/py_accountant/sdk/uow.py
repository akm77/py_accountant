"""SDK UoW factory helpers.

This module bridges SDK settings with the infrastructure async Unit of Work
implementation, exposing a small factory builder usable by apps.
"""
from __future__ import annotations

from collections.abc import Callable

from py_accountant.sdk.settings import Settings

try:  # Import infrastructure UoW with a user-friendly error on failure
    from infrastructure.persistence.sqlalchemy.uow import AsyncSqlAlchemyUnitOfWork
except Exception as _imp_err:  # pragma: no cover - rare import-time failure handling
    raise ValueError(
        "Infrastructure AsyncSqlAlchemyUnitOfWork is unavailable. Ensure project dependencies"
        " are installed and infrastructure package is importable."
    ) from _imp_err

__all__ = ["build_uow_factory", "AsyncSqlAlchemyUnitOfWork"]


def build_uow_factory(settings: Settings) -> Callable[[], AsyncSqlAlchemyUnitOfWork]:
    """Construct a factory that returns a fresh AsyncSqlAlchemyUnitOfWork on each call.

    The factory captures the async URL from settings. If it's missing, callers should
    provide it explicitly in tests by constructing Settings(async_url=...). The SDK does
    not implicitly convert sync URLs to async in production contexts.

    Returns:
        Callable that yields a new AsyncSqlAlchemyUnitOfWork when invoked.

    Raises:
        ValueError: if settings.async_url is not provided.
    """
    async_url = settings.async_url
    if not async_url:
        raise ValueError(
            "DATABASE_URL_ASYNC is required for runtime. Provide Settings(async_url=...) or set"
            " env DATABASE_URL_ASYNC. For quick local tests you may use 'sqlite+aiosqlite:///:memory:'."
        )

    def factory() -> AsyncSqlAlchemyUnitOfWork:
        return AsyncSqlAlchemyUnitOfWork(async_url)

    return factory

