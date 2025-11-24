"""Compatibility facade so that ``from domain.accounts import ...`` keeps working.

Delegates to ``py_accountant.domain.accounts``.
"""

from py_accountant.domain.accounts import *  # noqa: F401,F403

