"""Shared lightweight CLI infrastructure helpers (I22+).

Centralizes ephemeral async UnitOfWork creation and schema initialization for
CLI sub-apps (currencies/accounts/ledger/etc.) to keep command modules thin.

Design goals:
- No hidden global mutable state besides cached engine per URL (optional later).
- Idempotent schema creation (create_all) per invocation, acceptable for SQLite.
- Raise ValidationError if async infrastructure models/UoW not importable.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any, Protocol

from domain.errors import ValidationError

try:  # optional infra imports
    from infrastructure.persistence.sqlalchemy.models import Base  # type: ignore
    from infrastructure.persistence.sqlalchemy.uow import AsyncSqlAlchemyUnitOfWork  # type: ignore
except Exception:  # pragma: no cover
    AsyncSqlAlchemyUnitOfWork = None  # type: ignore
    Base = None  # type: ignore


class AsyncUowProtocol(Protocol):
    async def __aenter__(self) -> AsyncUowProtocol:
        ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: Any | None,
    ) -> None:
        ...


if TYPE_CHECKING:
    from infrastructure.persistence.sqlalchemy.uow import AsyncSqlAlchemyUnitOfWork as _AsyncUow
else:  # pragma: no cover - typing fallback
    _AsyncUow = Any


_DEFAULT_DB_URL_ASYNC = "sqlite+aiosqlite:///./py_accountant_cli.db"


def _resolve_url(url: str | None) -> str:
    return url or os.getenv("DATABASE_URL_ASYNC", _DEFAULT_DB_URL_ASYNC)


async def _prep_uow(url: str) -> _AsyncUow:
    if AsyncSqlAlchemyUnitOfWork is None or Base is None:  # pragma: no cover - infra missing
        raise ValidationError("Async infrastructure unavailable")
    uow = AsyncSqlAlchemyUnitOfWork(url)
    async with uow.engine.begin() as conn:  # type: ignore[attr-defined]
        await conn.run_sync(Base.metadata.create_all)
    return uow


def run_ephemeral_async_uow[UowT: AsyncUowProtocol, T](
    fn: Callable[[UowT], Awaitable[T]],
    url: str | None = None,
) -> T:
    """Run an async callable with a freshly prepared AsyncSqlAlchemyUnitOfWork.

    Steps:
    1. Resolve URL (env or provided).
    2. Create UoW and ensure schema (idempotent create_all).
    3. Enter transactional context, invoke fn(uow), auto-commit on success.

    Raises ValidationError if infrastructure missing. Propagates domain/use case
    exceptions for outer CLI error classification.
    """

    async def _driver() -> T:
        uow = await _prep_uow(_resolve_url(url))
        async with uow:  # type: ignore[arg-type]
            return await fn(uow)

    return asyncio.run(_driver())
