"""CLI application for py_accountant using Typer.

This example demonstrates how to create a command-line interface
for accounting operations using py_accountant with async support.
"""
from __future__ import annotations

import asyncio
from decimal import Decimal
from typing import Annotated

import typer
from rich.console import Console
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from py_accountant import __version_schema__
from py_accountant.application.dto.models import EntryLineDTO
from py_accountant.application.use_cases_async.accounts import (
    AsyncCreateAccount,
    AsyncGetAccount,
    AsyncListAccounts,
)
from py_accountant.application.use_cases_async.currencies import (
    AsyncCreateCurrency,
    AsyncListCurrencies,
    AsyncSetBaseCurrency,
)
from py_accountant.application.use_cases_async.ledger import AsyncPostTransaction
from py_accountant.infrastructure.migrations import MigrationError, MigrationRunner
from py_accountant.infrastructure.persistence.inmemory.clock import SystemClock
from py_accountant.infrastructure.persistence.sqlalchemy.uow import AsyncSqlAlchemyUnitOfWork

# Rich console for beautiful output
console = Console()

# Create Typer app
app = typer.Typer(
    name="accounting-cli",
    help="Command-line interface for py_accountant",
)

# Database configuration (in production, use config file or env vars)
DATABASE_URL = "sqlite+aiosqlite:///./accounting.db"

# Create async engine and session factory at module level
engine = create_async_engine(DATABASE_URL, echo=False)
session_factory = async_sessionmaker(engine, expire_on_commit=False)



# ============================================================================
# Database Migration Commands
# ============================================================================

@app.command("init-db")
def init_db():
    """Initialize database schema (run migrations)."""
    async def _init():
        console.print("[blue]Initializing database...[/blue]")

        # Create engine for migrations
        engine = create_async_engine(DATABASE_URL, echo=False)
        runner = MigrationRunner(engine, echo=True)

        try:
            # Check current state
            current = await runner.get_current_version()
            if current:
                console.print(f"Current version: [yellow]{current}[/yellow]")
            else:
                console.print("No migrations applied yet")

            # Run migrations
            console.print("[blue]Running migrations...[/blue]")
            await runner.upgrade_to_head()

            # Confirm success
            new_version = await runner.get_current_version()
            console.print(f"[green]✓[/green] Database initialized (version: {new_version})")

            # Check if version matches expected
            if new_version != __version_schema__:
                console.print("[yellow]Warning: Schema version mismatch[/yellow]")
                console.print(f"  Current: {new_version}")
                console.print(f"  Expected: {__version_schema__}")
            else:
                console.print(f"[green]✓[/green] Schema version validated: {new_version}")

        except MigrationError as e:
            console.print(f"[red]✗ Migration failed: {e}[/red]")
            raise typer.Abort() from e
        finally:
            await engine.dispose()

    asyncio.run(_init())


@app.command("check-db")
def check_db():
    """Check database migration status."""
    async def _check():
        engine = create_async_engine(DATABASE_URL, echo=False)
        runner = MigrationRunner(engine)

        try:
            current = await runner.get_current_version()
            pending = await runner.get_pending_migrations()

            console.print(f"Current version: [cyan]{current or 'None'}[/cyan]")
            console.print(f"Expected version: [cyan]{__version_schema__}[/cyan]")

            if pending:
                console.print(f"Pending migrations: [yellow]{len(pending)}[/yellow]")
                for migration in pending:
                    console.print(f"  • {migration}")
                console.print("\n[yellow]Run 'init-db' to apply pending migrations[/yellow]")
            else:
                console.print("[green]✓[/green] All migrations applied")

        finally:
            await engine.dispose()

    asyncio.run(_check())


# ============================================================================
# Currency Commands
# ============================================================================

@app.command("create-currency")
def create_currency_cmd(
    code: Annotated[str, typer.Argument(help="Currency code (e.g., USD, EUR)")],
    is_base: Annotated[bool, typer.Option("--base", help="Set as base currency")] = False,
):
    """Create a new currency."""
    async def _create():
        uow = AsyncSqlAlchemyUnitOfWork(session_factory)

        async with uow:
            # Create currency
            create_uc = AsyncCreateCurrency(uow=uow)
            currency = await create_uc(code=code)

            # Set as base if requested
            if is_base:
                set_base_uc = AsyncSetBaseCurrency(uow=uow)
                await set_base_uc(code=code)

            await uow.commit()

        typer.echo(f"✅ Currency created: {currency.code}" +
                   (" (base currency)" if is_base else ""))

    asyncio.run(_create())


@app.command("list-currencies")
def list_currencies_cmd():
    """List all currencies."""
    async def _list():
        uow = AsyncSqlAlchemyUnitOfWork(session_factory)

        async with uow:
            uc = AsyncListCurrencies(uow=uow)
            currencies = await uc()

        if not currencies:
            typer.echo("No currencies found.")
            return

        typer.echo("\n📊 Currencies:")
        typer.echo("-" * 40)
        for curr in currencies:
            base_marker = " ⭐ (BASE)" if curr.is_base else ""
            typer.echo(f"  {curr.code}{base_marker}")
        typer.echo("-" * 40)
        typer.echo(f"Total: {len(currencies)} currencies\n")

    asyncio.run(_list())


# ============================================================================
# Account Commands
# ============================================================================

@app.command("create-account")
def create_account_cmd(
    full_name: Annotated[str, typer.Argument(help="Account full name (e.g., Assets:Cash)")],
    currency: Annotated[str, typer.Argument(help="Currency code")],
):
    """Create a new account."""
    async def _create():
        uow = AsyncSqlAlchemyUnitOfWork(session_factory)

        async with uow:
            uc = AsyncCreateAccount(uow=uow)
            account = await uc(
                full_name=full_name,
                currency_code=currency,
            )
            await uow.commit()

        typer.echo(f"✅ Account created: {account.full_name} [{account.currency_code}] (ID: {account.id})")

    asyncio.run(_create())


@app.command("get-account")
def get_account_cmd(
    full_name: Annotated[str, typer.Argument(help="Account full name (e.g., Assets:Cash)")],
):
    """Get account details by full name."""
    async def _get():
        uow = AsyncSqlAlchemyUnitOfWork(session_factory)

        async with uow:
            uc = AsyncGetAccount(uow=uow)
            account = await uc(full_name=full_name)

        if not account:
            typer.echo(f"❌ Account '{full_name}' not found.")
            raise typer.Exit(1)

        typer.echo("\n📋 Account Details:")
        typer.echo("-" * 40)
        typer.echo(f"  ID: {account.id}")
        typer.echo(f"  Name: {account.full_name}")
        typer.echo(f"  Currency: {account.currency_code}")
        typer.echo("-" * 40 + "\n")

    asyncio.run(_get())


@app.command("list-accounts")
def list_accounts_cmd():
    """List all accounts."""
    async def _list():
        uow = AsyncSqlAlchemyUnitOfWork(session_factory)
        uc = AsyncListAccounts(uow=uow)

        async with uow:
            accounts = await uc()

        if not accounts:
            typer.echo("No accounts found.")
            return

        typer.echo("\n📊 Accounts:")
        typer.echo("-" * 60)
        for acc in accounts:
            typer.echo(f"  [{acc.id:3d}] {acc.full_name:30s} ({acc.currency_code})")
        typer.echo("-" * 60)
        typer.echo(f"Total: {len(accounts)} accounts\n")

    asyncio.run(_list())


# ============================================================================
# Transaction Commands
# ============================================================================

@app.command("post-transaction")
def post_transaction_cmd(
    from_account: Annotated[str, typer.Option("--from", help="Debit account name (e.g., Assets:Cash)")],
    to_account: Annotated[str, typer.Option("--to", help="Credit account name (e.g., Income:Salary)")],
    amount: Annotated[Decimal, typer.Argument(help="Transaction amount")],
    currency: Annotated[str, typer.Option("--currency", help="Currency code")] = "USD",
    description: Annotated[str, typer.Option("--desc", help="Transaction description")] = "",
):
    """Post a transaction between two accounts.

    Example:
        python cli.py post-transaction --from Assets:Cash --to Income:Salary 100.50 --desc "Payment"
    """
    async def _post():
        uow = AsyncSqlAlchemyUnitOfWork(session_factory)
        clock = SystemClock()
        uc = AsyncPostTransaction(uow=uow, clock=clock)

        async with uow:
            # Create entry lines with proper EntryLineDTO structure
            lines = [
                EntryLineDTO(
                    side="DEBIT",
                    account_full_name=from_account,
                    amount=amount,
                    currency_code=currency,
                ),
                EntryLineDTO(
                    side="CREDIT",
                    account_full_name=to_account,
                    amount=amount,
                    currency_code=currency,
                ),
            ]

            tx = await uc(
                lines=lines,
                memo=description or f"Transfer {amount} {currency}",
            )
            await uow.commit()

        typer.echo(f"✅ Transaction posted (ID: {tx.id})")
        typer.echo(f"   {amount} {currency} from {from_account} to {to_account}")
        if description:
            typer.echo(f"   Description: {description}")

    asyncio.run(_post())


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    app()

