"""Deprecated module: synchronous SQLAlchemy repositories have been removed in ASYNC-10.

Runtime is async-only now. Use infrastructure.persistence.sqlalchemy.repositories_async.
This module intentionally raises on import to surface migration needs in external code.
"""

raise ImportError(
    "Synchronous SQLAlchemy repositories are removed (ASYNC-10). "
    "Use 'infrastructure.persistence.sqlalchemy.repositories_async' instead."
)

