"""Compatibility package for deprecated ``application.interfaces`` namespace.

Existing imports such as ``from application.interfaces.ports import X`` are
expected to keep working; see ``application.interfaces.ports`` module.
"""

from py_accountant.application.interfaces import ports  # type: ignore[attr-defined]  # noqa: F401

__all__ = ["ports"]
