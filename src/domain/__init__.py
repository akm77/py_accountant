"""Compatibility facade for legacy imports.

Internal code and tests may import ``domain.*``.
Real installable package is ``py_accountant.domain.*``.
"""

from py_accountant.domain import *  # noqa: F401,F403

