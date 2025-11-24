"""Compatibility facade for DTO models package.

Provides ``application.dto.models`` as an alias for
``py_accountant.application.dto.models``.
"""

from py_accountant.application import dto as _core_dto  # noqa: F401

models = _core_dto.models

__all__ = ["models"]
