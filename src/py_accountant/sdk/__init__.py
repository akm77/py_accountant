"""Public SDK layer for py_accountant.

This package exposes thin facades over async use cases, a JSON presenter, and
public error types with exception mapping suitable for CLI/HTTP/bots.

Exports:
- json: JSON presenter helpers (to_dict, to_json)
- errors: public exceptions and map_exception()
- use_cases: thin async facades and SimpleTransactionParser
"""

from . import errors, json, use_cases  # re-export modules for convenient access

__all__ = ["json", "errors", "use_cases"]

