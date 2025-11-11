"""Domain error definitions.

This module provides the minimal, dependency‑free hierarchy of domain exceptions.
Public exceptions are used across the domain and use cases to signal validation
and invariant violations. Keep lean and stable.
"""

from __future__ import annotations

__all__ = ["DomainError", "ValidationError"]


class DomainError(Exception):
    """Base domain-layer error.

    Raised when a business rule or invariant is violated. All domain validation
    issues should raise (a subclass of) this error so callers can uniformly
    handle problems originating in the core model.
    """


class ValidationError(DomainError):
    """Specific domain validation error.

    Use when user/input data fails validation. Semantically narrower than
    DomainError; callers may choose to distinguish these cases.
    """

