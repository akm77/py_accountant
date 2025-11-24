"""Compatibility facade so that ``import domain.errors`` continues to work.

Real implementation lives in ``py_accountant.domain.errors``.
"""

from py_accountant.domain.errors import *  # noqa: F401,F403

