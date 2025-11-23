"""Public SDK layer for py_accountant.

This package exposes thin facades over async use cases, a JSON presenter, and
public error types with exception mapping suitable for CLI/HTTP/bots.

Exports:
- json: JSON presenter helpers (to_dict, to_json)
- errors: public exceptions and map_exception()
- use_cases: thin async facades and SimpleTransactionParser
- settings: Settings loader and dual-URL validation
- uow: Async UoW factory builder
- bootstrap: init_app/AppContext for one-import startup
"""

__all__ = [
    "json",
    "errors",
    "use_cases",
    "settings",
    "uow",
    "bootstrap",
    "reports",
]
