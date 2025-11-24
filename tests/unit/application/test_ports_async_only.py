"""Tests for unified async ports module (I11).

Ensures:
- application.ports exposes only async Protocol interfaces (no legacy sync names)
- Deprecated proxy application.interfaces.ports re-exports the same objects (identity check)
"""
from __future__ import annotations

import inspect

import py_accountant.application.interfaces.ports as deprecated_ports
from py_accountant.application import ports

# Legacy sync names that must be absent from the new unified module
LEGACY_SYNC_NAMES = {
    "UnitOfWork",  # sync UoW Protocol
    "CurrencyRepository",
    "AccountRepository",
    "TransactionRepository",
    "BalanceRepository",
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


def test_async_ports_public_surface_only_async():
    exported = set(getattr(ports, "__all__", []))
    assert EXPECTED_ASYNC.issubset(exported), "Missing async names in __all__"
    assert exported.isdisjoint(LEGACY_SYNC_NAMES), "Legacy sync names leaked into unified ports"
    # Ensure attributes exist and are Protocol subclasses (runtime_checkable marks them as Protocol instances)
    for name in EXPECTED_ASYNC:
        attr = getattr(ports, name, None)
        assert attr is not None, f"Missing {name}"
        assert inspect.isclass(attr), f"{name} not a class"


def test_deprecated_proxy_reexports_identity():
    for name in EXPECTED_ASYNC:
        new_obj = getattr(ports, name)
        old_obj = getattr(deprecated_ports, name)
        assert new_obj is old_obj, f"Proxy did not re-export same object for {name}"
    # Ensure removed async balance is not present
    assert not hasattr(ports, "AsyncBalanceRepository")


def test_no_legacy_sync_protocols_present():
    for legacy in LEGACY_SYNC_NAMES:
        assert not hasattr(ports, legacy), f"Legacy sync Protocol {legacy} must not be defined in application.ports"
