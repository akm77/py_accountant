from __future__ import annotations

import asyncio
import os
import sys
from datetime import UTC, datetime
from typing import Any

from typer import Typer

from domain.errors import DomainError, ValidationError

# NEW import for currencies sub-app
from . import currencies as currencies_module  # type: ignore

try:  # version import (fallback if metadata absent)
    from py_accountant import __version__ as _PKG_VERSION  # type: ignore
except Exception:  # pragma: no cover
    _PKG_VERSION = "unknown"

try:
    from infrastructure.persistence.sqlalchemy.uow import AsyncSqlAlchemyUnitOfWork  # type: ignore
except Exception:  # pragma: no cover - infra optional for help command
    AsyncSqlAlchemyUnitOfWork = None  # type: ignore

# === Constants & DI helpers ===
DEFAULT_DB_URL_ASYNC = "sqlite+aiosqlite:///:memory:"

_app_help = (
    "Async CLI foundation for py_accountant (I21). Future commands (currencies/accounts/ledger/"
    "trading/fx/report) will be added in I22+."
)

app: Typer = Typer(help=_app_help, add_completion=False)

diagnostics = Typer(help="Diagnostics and health checks (foundation).")
app.add_typer(diagnostics, name="diagnostics")
# Register currencies sub-app (I22)
app.add_typer(currencies_module.currencies, name="currency")


# Internal cached singletons (lazy)
_SINGLETONS: dict[str, Any] = {}


def _get_clock() -> Any:
    """Return a simple UTC clock object with now() method.

    The clock is a lightweight dependency used by async commands; it can be
    extended in future iterations (I22+) for injection/testing. Returns an
    object exposing a now() -> datetime[UTC] method.
    """
    clock = _SINGLETONS.get("clock")
    if clock is None:
        class _UTCClock:
            def now(self) -> datetime:  # pragma: no cover - trivial
                return datetime.now(UTC)
        clock = _UTCClock()
        _SINGLETONS["clock"] = clock
    return clock


def _get_uow() -> AsyncSqlAlchemyUnitOfWork | None:
    """Return (lazy) AsyncSqlAlchemyUnitOfWork instance or None.

    Reads DATABASE_URL_ASYNC from environment, falling back to an in-memory
    SQLite URL. Creation is deferred until the first command uses it (later
    iterations). Keeps a single instance per process for simplicity now.
    """
    if AsyncSqlAlchemyUnitOfWork is None:  # infra missing (help/version still work)
        return None
    uow = _SINGLETONS.get("uow")
    if uow is None:
        url = os.getenv("DATABASE_URL_ASYNC", DEFAULT_DB_URL_ASYNC)
        uow = AsyncSqlAlchemyUnitOfWork(url)
        _SINGLETONS["uow"] = uow
    return uow  # type: ignore[return-value]


# === Commands ===
@app.command("version")
async def version_cmd() -> None:
    """Print package version.

    Uses py_accountant.__version__ if available; falls back to 'unknown'. Output
    is a plain string to keep CLI interaction simple for scripting.
    """
    print(_PKG_VERSION)


@diagnostics.command("ping")
async def diagnostics_ping() -> None:
    """Basic async health check.

    Ensures an event loop is active and (optionally) that the async UoW can be
    constructed. Prints 'pong' on success; raises ValidationError on failure.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError as exc:
        raise ValidationError("No running event loop") from exc
    _get_uow()
    print("pong")


def _print_help() -> None:
    """Print minimal help message for the CLI foundation.

    Lists available top-level commands introduced in I21 to ensure a stable
    user experience even if the Typer/click stack isn't fully initialized.
    """
    print(
        "\n".join(
            [
                "Usage: py_accountant [OPTIONS] COMMAND [ARGS]...",
                "",
                "Async CLI foundation for py_accountant (I21). Future commands (I22+).",
                "",
                "Commands:",
                "  version            Show package version",
                "  diagnostics ping   Basic async health check (prints 'pong')",
            ]
        )
    )


def _predispatch(argv: list[str]) -> tuple[bool, int]:
    """Handle minimal commands without invoking Typer.

    Returns (handled, exit_code). Used to avoid dependency on click internals
    for the simplest scenarios (help/version/ping) in this iteration.
    """
    if not argv or argv[0] in {"-h", "--help"}:
        _print_help()
        return True, 0
    if argv == ["version"]:
        print(_PKG_VERSION)
        return True, 0
    if len(argv) == 2 and argv[0] == "diagnostics" and argv[1] == "ping":
        async def _do_ping() -> None:
            await diagnostics_ping()
        asyncio.run(_do_ping())
        return True, 0
    return False, 0


def cli(argv: list[str] | None = None) -> int:
    """Run Typer application with top-level error handling.

    Handles ValidationError (exit code 2) and unexpected exceptions (exit code 1).
    SystemExit passes through. Accepts optional argv for programmatic testing.
    Returns process-style exit code integer.
    """
    try:
        args = argv if argv is not None else sys.argv[1:]
        handled, code = _predispatch(args)
        if handled:
            return code
        if argv is not None:
            old_argv = sys.argv
            sys.argv = [old_argv[0]] + argv
            try:
                app()
            finally:
                sys.argv = old_argv
        else:
            app()
        return 0
    except ValidationError as ve:
        print(f"[ERROR] {ve}", file=sys.stderr)
        return 2
    except DomainError as de:
        print(f"[ERROR] {de}", file=sys.stderr)
        return 2
    except ValueError as ve:  # treat ValueError similarly (missing resource / duplicate)
        print(f"[ERROR] {ve}", file=sys.stderr)
        return 2
    except SystemExit as se:
        return int(se.code) if isinstance(se.code, int) else 0
    except Exception as exc:
        print(f"[ERROR] unexpected: {exc}", file=sys.stderr)
        return 1


def main(argv: list[str] | None = None) -> int:  # Legacy compatibility shim
    """Compatibility wrapper around cli().

    Existing tests imported presentation.cli.main.main([...]); keep name while migrating
    to async Typer CLI. Delegates directly to cli(). Will be removed in I27 when legacy
    sync bridge is deleted.
    """
    return cli(argv)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(cli())
