"""Compatibility facade for legacy imports.

Internal code and tests may import ``infrastructure.*``.
Real installable package is ``py_accountant.infrastructure.*``.
"""

from py_accountant.infrastructure import *  # noqa: F401,F403
