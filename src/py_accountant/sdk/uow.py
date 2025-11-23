"""SDK UoW factory helpers.

This module bridges SDK settings with the infrastructure async Unit of Work
implementation, exposing a small factory builder usable by apps.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Callable

from py_accountant.sdk.settings import Settings

# We intentionally avoid failing at import time if infrastructure is missing.
# Instead, we defer a clear error message until someone actually asks to build
# the default UoW factory.
try:  # pragma: no cover - exercised indirectly via build_uow_factory
    from infrastructure.persistence.sqlalchemy.uow import AsyncSqlAlchemyUnitOfWork
    _INFRA_IMPORT_ERROR: Exception | None = None
except Exception as exc:  # pragma: no cover - rare import-time failure handling
    AsyncSqlAlchemyUnitOfWork = object  # type: ignore[assignment]
    _INFRA_IMPORT_ERROR = exc

__all__ = ["build_uow_factory", "AsyncSqlAlchemyUnitOfWork"]


def build_uow_factory(settings: Settings) -> Callable[[], object]:
    """Construct a factory that returns a fresh AsyncSqlAlchemyUnitOfWork on each call.

    The factory captures the async URL from settings. If it's missing, callers should
    provide it explicitly in tests by constructing Settings(async_url=...). The SDK does
    not implicitly convert sync URLs to async in production contexts.

    Returns:
        Callable that yields a new AsyncSqlAlchemyUnitOfWork when invoked.

    Raises:
        RuntimeError: if the infrastructure AsyncSqlAlchemyUnitOfWork cannot be imported.
        ValueError: if settings.async_url is not provided.
    """
    if _INFRA_IMPORT_ERROR is not None:
        raise RuntimeError(
            "py_accountant infrastructure AsyncSqlAlchemyUnitOfWork is unavailable. "
            "Ensure that the 'infrastructure' package is importable in your environment, "
            "or provide a custom UoW factory instead of using the default one from sdk.uow."
        ) from _INFRA_IMPORT_ERROR

    async_url = settings.async_url
    if not async_url:
        raise ValueError(
            "DATABASE_URL_ASYNC is required for runtime. Provide Settings(async_url=...) or set "
            "env DATABASE_URL_ASYNC. For quick local tests you may use 'sqlite+aiosqlite:///:memory:'."
        )

    def factory() -> AsyncSqlAlchemyUnitOfWork:
        return AsyncSqlAlchemyUnitOfWork(async_url)

    return factory
