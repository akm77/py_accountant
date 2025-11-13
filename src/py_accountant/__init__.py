"""Top-level package for py_accountant.

Provides a minimal public API and exposes the distribution version.
"""

from importlib import metadata as _metadata

try:  # Attempt to read the installed package version
    __version__ = _metadata.version("py-accountant")
except _metadata.PackageNotFoundError:  # Fallback when running from source without install
    __version__ = "0.0.0.dev"

# Re-export SDK namespace for stable imports
from . import sdk  # noqa: E402
from .sdk import bootstrap, errors, json, settings, uow, use_cases  # noqa: E402

__all__ = [
    "__version__",
    "get_version",
    "add",
    "sdk",
    "json",
    "errors",
    "use_cases",
    "bootstrap",
    "settings",
    "uow",
]


def get_version() -> str:
    """Return the package version string."""
    return __version__


def add(a: float, b: float) -> float:
    """Example function to demonstrate import usage.

    Args:
        a: First number.
        b: Second number.
    Returns:
        Sum of a and b.
    """
    return a + b
