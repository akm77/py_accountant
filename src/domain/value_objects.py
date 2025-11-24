"""Compatibility facade for legacy ``domain.value_objects`` imports.

Modern layout keeps value objects under dedicated modules like
``py_accountant.domain.tx``, ``py_accountant.domain.currencies`` etc.

This shim exposes a minimal subset for older tests and integrations.
"""

from py_accountant.domain.currencies import CurrencyCode  # noqa: F401
from py_accountant.domain.errors import DomainError  # noqa: F401

__all__ = ["CurrencyCode", "DomainError"]
