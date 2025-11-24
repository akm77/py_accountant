"""Compatibility facade so that ``from domain.currencies import ...`` keeps working.

Delegates to ``py_accountant.domain.currencies``.
 """

from py_accountant.domain.currencies import *  # noqa: F401,F403
