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
from py_accountant.application.use_cases_async.accounts import (
    AsyncCreateAccount,
    AsyncGetAccount,
    AsyncListAccounts,
)
from py_accountant.application.use_cases_async.currencies import (
    AsyncCreateCurrency,
    AsyncListCurrencies,
)
from py_accountant.application.use_cases_async.ledger import (
    AsyncPostTransaction,
)
from py_accountant.infrastructure.migrations import MigrationError, MigrationRunner
from py_accountant.infrastructure.persistence.sqlalchemy.repositories_async import (
    AsyncSqlAlchemyAccountRepository,
    AsyncSqlAlchemyCurrencyRepository,
    AsyncSqlAlchemyLedgerRepository,
)
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


def get_dependencies():
    """Create dependencies for use cases.

    Returns:
        Tuple of (uow, account_repo, currency_repo, ledger_repo)
    """
    uow = AsyncSqlAlchemyUnitOfWork(session_factory)
    account_repo = AsyncSqlAlchemyAccountRepository()
    currency_repo = AsyncSqlAlchemyCurrencyRepository()
    ledger_repo = AsyncSqlAlchemyLedgerRepository()

    return uow, account_repo, currency_repo, ledger_repo


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
            raise typer.Abort()
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
        uow, _, currency_repo, _ = get_dependencies()
        uc = AsyncCreateCurrency(currency_repo=currency_repo, uow=uow)

        async with uow:
            currency = await uc.execute(code=code, is_base=is_base)
            await uow.commit()

        typer.echo(f"✅ Currency created: {currency.code}" +
                   (" (base currency)" if is_base else ""))

    asyncio.run(_create())


@app.command("list-currencies")
def list_currencies_cmd():
    """List all currencies."""
    async def _list():
        uow, _, currency_repo, _ = get_dependencies()
        uc = AsyncListCurrencies(currency_repo=currency_repo, uow=uow)

        async with uow:
            currencies = await uc.execute()

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
        uow, account_repo, currency_repo, _ = get_dependencies()
        uc = AsyncCreateAccount(
            account_repo=account_repo,
            currency_repo=currency_repo,
            uow=uow,
        )

        async with uow:
            account = await uc.execute(
                full_name=full_name,
                currency_code=currency,
            )
            await uow.commit()

        typer.echo(f"✅ Account created: {account.full_name} [{account.currency_code}] (ID: {account.id})")

    asyncio.run(_create())


@app.command("get-account")
def get_account_cmd(
    account_id: Annotated[int, typer.Argument(help="Account ID")],
):
    """Get account details by ID."""
    async def _get():
        uow, account_repo, _, _ = get_dependencies()
        uc = AsyncGetAccount(account_repo=account_repo, uow=uow)

        async with uow:
            account = await uc.execute(account_id=account_id)

        if not account:
            typer.echo(f"❌ Account {account_id} not found.")
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
        uow, account_repo, _, _ = get_dependencies()
        uc = AsyncListAccounts(account_repo=account_repo, uow=uow)

        async with uow:
            accounts = await uc.execute()

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
    from_account: Annotated[int, typer.Option("--from", help="Debit account ID")],
    to_account: Annotated[int, typer.Option("--to", help="Credit account ID")],
    amount: Annotated[Decimal, typer.Argument(help="Transaction amount")],
    description: Annotated[str, typer.Option("--desc", help="Transaction description")] = "",
):
    """Post a transaction between two accounts.

    Example:
        accounting-cli post-transaction --from 1 --to 2 100.50 --desc "Payment"
    """
    async def _post():
        uow, account_repo, _, ledger_repo = get_dependencies()
        uc = AsyncPostTransaction(
            ledger_repo=ledger_repo,
            account_repo=account_repo,
            uow=uow,
        )

        async with uow:
            entry = await uc.execute(
                lines=[
                    {"account_id": from_account, "debit": amount, "credit": Decimal("0")},
                    {"account_id": to_account, "debit": Decimal("0"), "credit": amount},
                ],
                description=description or f"Transfer {amount}",
            )
            await uow.commit()

        typer.echo(f"✅ Transaction posted (Entry ID: {entry.id})")
        typer.echo(f"   {amount} from account {from_account} to account {to_account}")
        if description:
            typer.echo(f"   Description: {description}")

    asyncio.run(_post())


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    app()

