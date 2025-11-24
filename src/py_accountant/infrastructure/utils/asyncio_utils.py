from __future__ import annotations

import asyncio as _asyncio
from collections.abc import Coroutine
from contextlib import suppress
from typing import Any


def run_sync[T](coro: Coroutine[Any, Any, T]) -> T:
    """Run an async coroutine from a synchronous context safely.

    Purpose:
    - Provide a minimal and safe way to execute async use cases from the
      synchronous CLI without introducing nested event loops.

    Behavior:
    - If an event loop is already running in the current thread, raise a
      RuntimeError with a clear guidance message to call the async API directly.
    - Otherwise, drive the coroutine to completion using ``asyncio.run`` and
      return the result.

    Parameters:
    - coro: A coroutine object to run to completion (not a generic Awaitable).

    Returns:
    - The value returned by the awaited coroutine.

    Raises:
    - RuntimeError: if called from within an already running event loop.
    - Any exception raised by the coroutine itself will be propagated as-is.

    Notes:
    - To avoid a "coroutine was never awaited" warning when rejecting due to an
      active loop, the coroutine is explicitly ``close()``-ed before raising.
    - No third-party libraries are used; strictly stdlib asyncio.
    """
    try:
        _asyncio.get_running_loop()
    except RuntimeError:
        return _asyncio.run(coro)
    # Active loop detected: close coroutine to prevent un-awaited warning
    with suppress(Exception):
        coro.close()
    raise RuntimeError(
        "run_sync() cannot be used inside an active event loop. "
        "Call the async API directly from async code."
    )
