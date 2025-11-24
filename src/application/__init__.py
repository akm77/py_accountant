"""Compatibility facade for legacy imports.

Internal code and tests may import ``application.*``.
Real installable package is ``py_accountant.application.*``.
"""

from py_accountant import application as _core_app  # noqa: F401

# Re-export everything from core application for convenience
from py_accountant.application import *  # noqa: F401,F403

# Expose common subpackages explicitly for compatibility
from . import dto, use_cases_async  # noqa: F401

ports = _core_app.ports

__all__ = [
    *[name for name in globals() if not name.startswith("_")],
    "dto",
    "use_cases_async",
    "ports",
]
