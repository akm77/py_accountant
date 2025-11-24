"""Compatibility facade for logging configuration.

Legacy imports like ``from infrastructure.logging.config import ...`` are
redirected to ``py_accountant.infrastructure.logging.config``.
"""

from py_accountant.infrastructure.logging import *  # noqa: F401,F403

