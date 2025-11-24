"""Compatibility facade so that ``from domain.quantize import ...`` keeps working.

Delegates to ``py_accountant.domain.quantize``.
"""

from py_accountant.domain.quantize import *  # noqa: F401,F403

