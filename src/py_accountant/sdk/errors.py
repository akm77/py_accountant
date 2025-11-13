"""SDK public error classes and exception mapping.

This module defines lightweight exceptions for consumers of the SDK and a
single mapping function that converts internal domain/application exceptions
into public ones without losing the original message.

Public exceptions:
- UserInputError: invalid user input or format
- DomainViolation: domain invariant violations
- NotFound: requested resource is missing
- UnexpectedError: any other error not classified above

map_exception(exc) keeps the original message and returns an instance of the
public exception type best matching the input.
"""
from __future__ import annotations

from domain.errors import DomainError, ValidationError

__all__ = [
    "UserInputError",
    "DomainViolation",
    "NotFound",
    "UnexpectedError",
    "map_exception",
]


class UserInputError(Exception):
    """Raised when user input is invalid or cannot be parsed.

    Keep messages concise; callers may present them directly to users.
    """


class DomainViolation(Exception):
    """Raised when domain/business rules are violated."""


class NotFound(Exception):
    """Raised when a referenced resource does not exist."""


class UnexpectedError(Exception):
    """Raised when an unexpected error occurs inside the SDK/use cases."""


def map_exception(exc: Exception) -> Exception:
    """Map internal exceptions to public SDK exceptions.

    Rules:
    - ValidationError -> UserInputError
    - DomainError -> DomainViolation
    - ValueError -> UserInputError (could be NotFound, but avoid guessing)
    - any other -> UnexpectedError

    The returned exception carries the original text message.
    """
    msg = str(exc)
    # Preserve exact classification for domain validation first
    if isinstance(exc, ValidationError):
        return UserInputError(msg)
    # Other domain errors (invariants) map to DomainViolation
    if isinstance(exc, DomainError):
        return DomainViolation(msg)
    # ValueError commonly used for missing resources or bad inputs in app layer
    if isinstance(exc, ValueError):
        return UserInputError(msg)
    # Fallback
    return UnexpectedError(msg)

