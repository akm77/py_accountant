"""DEPRECATED sync repositories (I28).

All synchronous repository classes are stubs raising RuntimeError on instantiation.
Use async repositories in repositories_async.py instead. Will be removed in a future iteration.
"""

from __future__ import annotations

import warnings

__all__ = [
    "SqlAlchemyCurrencyRepository",
    "SqlAlchemyAccountRepository",
    "SqlAlchemyTransactionRepository",
    "SqlAlchemyBalanceRepository",
    "SqlAlchemyExchangeRateEventsRepository",
]

MESSAGE = (
    "DEPRECATED: synchronous repositories have been removed from active architecture. "
    "Use async implementations in repositories_async.py (CRUD-only). This stub will be deleted in a future iteration."
)


def _deprecated(name: str) -> None:
    """Emit a DeprecationWarning and raise RuntimeError for a deprecated sync repo.

    This helper ensures a single, predictable message for all stub classes.
    """
    warnings.warn(MESSAGE, DeprecationWarning, stacklevel=2)
    raise RuntimeError(f"{name}: {MESSAGE}")


class SqlAlchemyCurrencyRepository:
    """DEPRECATED sync repository stub for currencies. Use AsyncSqlAlchemyCurrencyRepository."""

    def __init__(self, *args, **kwargs) -> None:  # noqa: D401
        """Constructor raises deprecation error to block usage."""
        _deprecated(self.__class__.__name__)


class SqlAlchemyAccountRepository:
    """DEPRECATED sync repository stub for accounts. Use AsyncSqlAlchemyAccountRepository."""

    def __init__(self, *args, **kwargs) -> None:  # noqa: D401
        """Constructor raises deprecation error to block usage."""
        _deprecated(self.__class__.__name__)


class SqlAlchemyTransactionRepository:
    """DEPRECATED sync repository stub for transactions. Use AsyncSqlAlchemyTransactionRepository."""

    def __init__(self, *args, **kwargs) -> None:  # noqa: D401
        """Constructor raises deprecation error to block usage."""
        _deprecated(self.__class__.__name__)


class SqlAlchemyBalanceRepository:
    """DEPRECATED sync repository stub for balance cache. Use AsyncSqlAlchemyBalanceRepository."""

    def __init__(self, *args, **kwargs) -> None:  # noqa: D401
        """Constructor raises deprecation error to block usage."""
        _deprecated(self.__class__.__name__)


class SqlAlchemyExchangeRateEventsRepository:
    """DEPRECATED sync repository stub for FX audit events. Use AsyncSqlAlchemyExchangeRateEventsRepository."""

    def __init__(self, *args, **kwargs) -> None:  # noqa: D401
        """Constructor raises deprecation error to block usage."""
        _deprecated(self.__class__.__name__)
