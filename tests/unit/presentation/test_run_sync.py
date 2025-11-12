from __future__ import annotations

import asyncio

import pytest

from infrastructure.utils.asyncio_utils import run_sync


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
