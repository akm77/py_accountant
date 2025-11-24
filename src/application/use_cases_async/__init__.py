"""Compatibility facade package for async application use cases.

Allows imports like ``from application.use_cases_async import ledger`` to
continue working. Real implementations live under
``py_accountant.application.use_cases_async``.
"""

from py_accountant.application.use_cases_async import *  # noqa: F401,F403
from py_accountant.application.use_cases_async import ledger  # noqa: F401

__all__ = ["ledger"]
