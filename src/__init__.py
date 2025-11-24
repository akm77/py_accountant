"""Compatibility facade for legacy imports.

The real installable package is ``py_accountant`` (under src/py_accountant).

To avoid breaking existing internal imports (e.g. ``from application...`` or
``from domain...``) within this repository, we provide minimal re-exports from
this compatibility module.

External consumers should import from ``py_accountant.*`` instead.
"""

from .py_accountant import application, domain, infrastructure  # noqa: F401

