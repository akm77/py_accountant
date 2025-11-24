"""Compatibility facade for infrastructure.config.

Legacy imports like ``from infrastructure.config.settings import ...`` are
redirected to ``py_accountant.infrastructure.config.settings``.
"""

from py_accountant.infrastructure.config import *  # noqa: F401,F403
