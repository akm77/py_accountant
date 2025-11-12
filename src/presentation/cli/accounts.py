"""Async account management CLI commands (I23).

Provides Typer sub-app with minimal commands: list, add (and optional get).
Thin controller orchestrating async use cases; human output by default, JSON
when --json flag is provided. Error classification is handled by top-level
cli() in main.py (success=0, validation/domain/value errors=2, unexpected=1).
"""
from __future__ import annotations

import json
from collections.abc import Iterable

from typer import Option, Typer

from application.use_cases_async.accounts import (
    AsyncCreateAccount,
    AsyncGetAccount,
    AsyncListAccounts,
)
from domain.errors import ValidationError

from .infra import run_ephemeral_async_uow

accounts = Typer(help="Account management (async): list, add, get.")


def _to_public_dicts(dtos: Iterable) -> list[dict[str, str]]:
    # DTO -> JSON-safe public shape with stable keys
    return [{"full_name": a.full_name, "currency_code": a.currency_code} for a in dtos]


@accounts.command("list")
def account_list(
    json_output: bool = Option(False, "--json", help="Output JSON instead of human-readable lines."),
) -> None:
    """List all accounts.

    Parameters:
        json_output: When True prints JSON array of {full_name,currency_code} objects.
    Notes:
        List is sorted lexicographically by full_name for deterministic output.
    """
    async def _logic(uow):
        return await AsyncListAccounts(uow)()

    dtos = run_ephemeral_async_uow(_logic)
    # Deterministic order for output stability
    dtos = sorted(dtos, key=lambda d: d.full_name)
    if json_output:
        print(json.dumps(_to_public_dicts(dtos)))
        return
    for a in dtos:
        print(f"Account {a.full_name} currency={a.currency_code}")


@accounts.command("add")
def account_add(
    full_name: str,
    currency_code: str,
    json_output: bool = Option(False, "--json", help="Output JSON object for created account."),
) -> None:
    """Add a new account.

    Args:
        full_name: Hierarchical name (segments ':'), validated in domain.
        currency_code: Associated currency (upper normalized).
        json_output: If True prints JSON object.
    Errors:
        ValidationError/ValueError mapped to exit code 2 by main.cli.
    """
    norm_full = (full_name or "").strip()
    norm_code = (currency_code or "").strip().upper()
    if not norm_full:
        raise ValidationError("Empty account full_name")
    if not norm_code:
        raise ValidationError("Empty currency code")

    async def _logic(uow):
        dto = await AsyncCreateAccount(uow)(norm_full, norm_code)
        return dto

    dto = run_ephemeral_async_uow(_logic)
    if json_output:
        print(json.dumps({"full_name": dto.full_name, "currency_code": dto.currency_code}))
        return
    print(f"Account {dto.full_name} currency={dto.currency_code}")


@accounts.command("get")
def account_get(
    full_name: str,
    json_output: bool = Option(False, "--json", help="Output JSON object if found."),
) -> None:
    """Get account by full_name.

    Args:
        full_name: Hierarchical account name.
        json_output: If True prints JSON object.
    Errors:
        ValidationError mapped to exit code 2 when account not found or name empty.
    """
    norm_full = (full_name or "").strip()
    if not norm_full:
        raise ValidationError("Empty account full_name")

    async def _logic(uow):
        return await AsyncGetAccount(uow)(norm_full)

    dto = run_ephemeral_async_uow(_logic)
    if dto is None:
        raise ValidationError("Account not found")
    if json_output:
        print(json.dumps({"full_name": dto.full_name, "currency_code": dto.currency_code}))
        return
    print(f"Account {dto.full_name} currency={dto.currency_code}")

