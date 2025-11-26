"""Top-level package for py_accountant.

This package groups the public core modules of the project under
`py_accountant.*` so the library can be imported as a dependency.

Source of truth for structure: `rpg_py_accountant.yaml`.
"""

from __future__ import annotations

__version__ = "1.1.0"
__version_schema__ = "0008_add_account_aggregates"

__version_schema__: str
"""Database schema version (last migration file name).

Used to verify that the application code is compatible with the database schema.
Should match the latest migration in alembic/versions/.

Example:
    >>> from py_accountant import __version_schema__
    >>> print(__version_schema__)
    '0008_add_account_aggregates'
"""

__all__ = [
    "__version__",
    "__version_schema__",
]

