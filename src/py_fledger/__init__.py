from __future__ import annotations

import warnings

from .book import Book, FError, book

warnings.warn(
    "Importing py_fledger is deprecated; migrate to py_accountant application use cases.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["Book", "FError", "book"]
