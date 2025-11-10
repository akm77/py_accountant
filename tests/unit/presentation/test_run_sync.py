from __future__ import annotations

import asyncio

import pytest

from infrastructure.utils.asyncio_utils import run_sync
from presentation.async_bridge import create_currency_sync, list_currencies_sync


def test_run_sync_outside_event_loop():
    async def coro():
        return 42
    assert run_sync(coro()) == 42


def test_run_sync_inside_event_loop_error():
    async def inner():
        async def coro():
            return 1
        with pytest.raises(RuntimeError) as exc:
            run_sync(coro())  # nested loop not allowed
        assert "cannot be used inside an active event loop" in str(exc.value)
    asyncio.run(inner())


def test_currency_facade_smoke_memory_isolation(monkeypatch):
    # Ensure isolation via PYTEST_CURRENT_TEST env influences keying
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "facade_smoke")
    # Create currency and list
    dto = create_currency_sync("USD")
    assert dto.code == "USD"
    all_cur = list_currencies_sync()
    assert any(c.code == "USD" for c in all_cur)


def test_currency_facade_domain_error(monkeypatch):
    # Attempt double base set on missing currency should raise DomainError
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "facade_error")
    from domain.value_objects import DomainError
    with pytest.raises(DomainError):
        # set_base requires existing currency
        from presentation.async_bridge import set_base_currency_sync
        set_base_currency_sync("EUR")
