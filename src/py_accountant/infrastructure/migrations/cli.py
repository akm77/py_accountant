"""CLI commands for py_accountant migrations."""

import asyncio
import os
import sys
from pathlib import Path

import typer
from alembic import command
from alembic.config import Config
from rich.console import Console
from rich.table import Table
from sqlalchemy.ext.asyncio import create_async_engine

from .runner import MigrationRunner

app = typer.Typer(
    name="migrations",
    help="Manage py_accountant database migrations",
    pretty_exceptions_enable=False,
)
console = Console()


def get_database_url() -> str:
    """Get DATABASE_URL from environment."""
    url = os.getenv("DATABASE_URL") or os.getenv("PYACC__DATABASE_URL")
    if not url:
        console.print("[red]Error: DATABASE_URL not set[/red]", file=sys.stderr)
        sys.exit(1)
    return url


@app.command()
def upgrade(
    revision: str = typer.Argument("head", help="Target revision"),
    echo: bool = typer.Option(False, "--echo", help="Echo SQL"),
):
    """Apply migrations."""

    url = get_database_url()
    # Ensure echo is boolean (typer may pass string from env vars)
    echo_bool = bool(echo) if not isinstance(echo, bool) else echo
    engine = create_async_engine(url, echo=echo_bool)
    runner = MigrationRunner(engine, echo=echo_bool)

    console.print(f"[blue]Upgrading to {revision}...[/blue]")
    if revision == "head":
        asyncio.run(runner.upgrade_to_head())
    else:
        asyncio.run(runner.upgrade_to_version(revision))
    console.print("[green]✓ Successfully upgraded[/green]")


@app.command()
def downgrade(
    revision: str,
    echo: bool = typer.Option(False, "--echo"),
):
    """Rollback migrations.

    Args:
        revision: Target revision or -N (e.g., -1, -2, or base)
    """
    url = get_database_url()
    # Ensure echo is boolean (typer may pass string from env vars)
    echo_bool = bool(echo) if not isinstance(echo, bool) else echo
    engine = create_async_engine(url, echo=echo_bool)
    runner = MigrationRunner(engine, echo=echo_bool)

    console.print(f"[yellow]Downgrading to {revision}...[/yellow]")
    asyncio.run(runner.downgrade(target=revision))
    console.print("[green]✓ Successfully downgraded[/green]")


@app.command()
def current(echo: bool = typer.Option(False, "--echo")):
    """Show current schema version."""

    url = get_database_url()
    # Ensure echo is boolean (typer may pass string from env vars)
    echo_bool = bool(echo) if not isinstance(echo, bool) else echo
    engine = create_async_engine(url, echo=echo_bool)
    runner = MigrationRunner(engine, echo=echo_bool)

    current_version = asyncio.run(runner.get_current_version())

    if current_version:
        console.print(f"[green]Current version: {current_version}[/green]")
    else:
        console.print("[yellow]Database not initialized[/yellow]")


@app.command()
def pending(echo: bool = typer.Option(False, "--echo")):
    """Show pending migrations."""

    url = get_database_url()
    # Ensure echo is boolean (typer may pass string from env vars)
    echo_bool = bool(echo) if not isinstance(echo, bool) else echo
    engine = create_async_engine(url, echo=echo_bool)
    runner = MigrationRunner(engine, echo=echo_bool)

    pending_migrations = asyncio.run(runner.get_pending_migrations())

    if not pending_migrations:
        console.print("[green]✓ No pending migrations[/green]")
        return

    table = Table(title="Pending Migrations")
    table.add_column("Revision", style="cyan")

    for rev in pending_migrations:
        table.add_row(rev)

    console.print(table)
    console.print(f"\n[yellow]{len(pending_migrations)} pending[/yellow]")


@app.command()
def history(echo: bool = typer.Option(False, "--echo")):
    """Show migration history."""

    migrations_dir = Path(__file__).parent
    config = Config()
    config.set_main_option("script_location", str(migrations_dir))

    command.history(config)

