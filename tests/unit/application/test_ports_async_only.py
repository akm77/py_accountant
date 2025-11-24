"""Tests for unified ports module (post-cleanup).

Ensures:
- application.ports exposes both async (primary) and sync (legacy) Protocol interfaces
- Async interfaces are the main public API
- Sync interfaces kept for backward compatibility with inmemory adapters and sync use cases
- application.interfaces.ports removed (no longer needed)
"""
from __future__ import annotations

import inspect

from py_accountant.application import ports

# Sync protocols (now part of main ports module for backward compatibility)
EXPECTED_SYNC = {
    "UnitOfWork",
    "CurrencyRepository",
    "AccountRepository",
    "TransactionRepository",
    "ExchangeRateEventsRepository",
}

EXPECTED_ASYNC = {
    "Clock",
    "SupportsCommitRollback",
    "AsyncCurrencyRepository",
    "AsyncAccountRepository",
    "AsyncTransactionRepository",
    "AsyncExchangeRateEventsRepository",
    "AsyncUnitOfWork",
}


def test_ports_public_surface_contains_all():
    """Verify all async and sync protocols are in __all__."""
    exported = set(getattr(ports, "__all__", []))
    assert EXPECTED_ASYNC.issubset(exported), "Missing async names in __all__"
    assert EXPECTED_SYNC.issubset(exported), "Missing sync names in __all__"
    # Ensure attributes exist and are Protocol subclasses
    for name in EXPECTED_ASYNC | EXPECTED_SYNC:
        attr = getattr(ports, name, None)
        assert attr is not None, f"Missing {name}"
        assert inspect.isclass(attr), f"{name} not a class"


def test_async_balance_repository_removed():
    """AsyncBalanceRepository was removed in favor of fast-path get_balance."""
    assert not hasattr(ports, "AsyncBalanceRepository")


def test_interfaces_module_removed():
    """application.interfaces.ports module should be removed."""
    try:
        import py_accountant.application.interfaces.ports  # noqa: F401
        assert False, "application.interfaces.ports should not exist anymore"
    except ModuleNotFoundError:
        pass  # Expected
