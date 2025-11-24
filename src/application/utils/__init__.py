"""Compatibility facade for application-level utilities.

Legacy imports like ``from application.utils.quantize import ...`` are
redirected to ``py_accountant.domain.quantize``.
"""

from types import ModuleType

import py_accountant.domain.quantize as _quantize

quantize: ModuleType = _quantize  # type: ignore[assignment]

__all__ = ["quantize"]
