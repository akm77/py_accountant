"""SDK bootstrap: init application context with validated settings and UoW.

Provides a single entrypoint ``init_app`` that loads or accepts Settings, validates
dual-URL policy, constructs a UoW factory, and returns an AppContext with a simple
UTC clock and a basic logger.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol, runtime_checkable

from application.ports import Clock as ClockProtocol
from py_accountant.sdk.settings import Settings, load_from_env, validate_dual_url
from py_accountant.sdk.uow import build_uow_factory

__all__ = ["AppContext", "init_app"]


@runtime_checkable
class AsyncUnitOfWorkProtocol(Protocol):  # pragma: no cover - structural typing helper
    """Minimal async UoW protocol used by the SDK.

    This mirrors the shape of AsyncSqlAlchemyUnitOfWork sufficiently for SDK use
    and allows external projects to provide their own implementation if needed.
    """

    async def __aenter__(self) -> AsyncUnitOfWorkProtocol: ...  # noqa: D401

    async def __aexit__(self, exc_type, exc, tb) -> None: ...  # noqa: D401


@dataclass(slots=True)
class _UtcClock:
    """Minimal UTC clock implementation compatible with application.ports.Clock."""

    def now(self) -> datetime:  # noqa: D401 - short and clear
        """Return current UTC time with tzinfo=UTC and zero microseconds."""
        return datetime.now(UTC).replace(microsecond=0)


@dataclass(slots=True)
class AppContext:
    """Application bootstrap context for SDK users.

    Attributes:
        uow_factory: Callable producing async UnitOfWork instances.
        clock: UTC clock object with now() -> datetime.
        logger: A configured logging.Logger.
        settings: Validated Settings instance used to configure the app.
    """

    uow_factory: Callable[[], AsyncUnitOfWorkProtocol]
    clock: ClockProtocol
    logger: logging.Logger
    settings: Settings


def init_app(settings: Settings | None = None, *, use_env: bool = True) -> AppContext:
    """Initialize the application context for SDK consumers.

    Steps:
    1) Load Settings from env if not provided and use_env=True.
    2) Validate dual-URL policy (raises ValueError on mismatch).
    3) Build UoW factory using settings.async_url.
    4) Create a UTC clock and a basic logger.

    Notes:
    - No I/O is performed here; database connections are only established when
      a UoW is created and used via "async with".

    Raises:
    - ValueError: if URLs are invalid or async URL is missing for runtime.
    """
    if settings is None:
        if not use_env:
            raise ValueError("settings must be provided when use_env=False")
        settings = load_from_env()

    validate_dual_url(settings)

    # Build UoW factory (requires async_url); this will raise a clear error if
    # the default infrastructure UoW is not available in the installed package.
    uow_factory = build_uow_factory(settings)

    # Minimal logger; do not configure handlers here to avoid side effects
    logger = logging.getLogger("py_accountant")

    ctx = AppContext(uow_factory=uow_factory, clock=_UtcClock(), logger=logger, settings=settings)
    return ctx
