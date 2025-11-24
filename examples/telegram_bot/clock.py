"""Clock provider for telegram bot."""
from __future__ import annotations

from py_accountant.application.ports import Clock
from py_accountant.infrastructure.persistence.inmemory.clock import SystemClock


def create_clock() -> Clock:
    """Create clock instance for bot.

    Returns:
        SystemClock instance (always UTC).

    Notes:
        SystemClock always returns datetime.now(UTC).
        If you need user-specific timezones, use UserTimezoneClock wrapper.

    Example:
        >>> clock = create_clock()
        >>> now = clock.now()
        >>> print(now)  # 2025-01-15 10:30:00+00:00
    """
    return SystemClock()

