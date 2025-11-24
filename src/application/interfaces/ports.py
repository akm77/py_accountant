"""Backwards-compatibility shim for ``application.interfaces.ports``.

Historically protocols lived under this namespace. Modern layout consolidates
ports in ``py_accountant.application.ports``.

Tests and external code using ``from application.interfaces.ports import X``
can continue to do so; all names are re-exported from the core module.
"""

from py_accountant.application.ports import *  # noqa: F401,F403

