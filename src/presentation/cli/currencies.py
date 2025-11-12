"""Async currency management CLI commands (I22).

Provides minimal Typer sub-app with three commands: list, add, set-base. Thin
controller layer orchestrating async use cases (CRUD-only repos). Human output
by default; --json flag for structured scripting. Validation/Domain/ValueError
handled by top-level cli() in main.py (exit codes: success=0, errors=2).
"""
from __future__ import annotations

import json
import os
from decimal import Decimal

from typer import Option, Typer

from application.use_cases_async.currencies import (
    AsyncCreateCurrency,
    AsyncListCurrencies,
    AsyncSetBaseCurrency,
)
from domain.errors import ValidationError

from .infra import run_ephemeral_async_uow  # shared helper

_DEFAULT_DB_URL_ASYNC = "sqlite+aiosqlite:///./py_accountant_cli.db"

currencies = Typer(help="Currency management: list, add, set-base (async use cases).")


def _env_url() -> str:
    return os.getenv("DATABASE_URL_ASYNC", _DEFAULT_DB_URL_ASYNC)


@currencies.command("list")
def currency_list(
    json_output: bool = Option(False, "--json", help="Output JSON instead of human-readable lines."),
) -> None:
    """List all currencies.

    Parameters:
        json_output: When True prints a JSON array of {code,is_base,exchange_rate} objects.
    Errors:
        ValidationError when infrastructure missing.
    """
    async def _logic(uow):  # uow type: AsyncSqlAlchemyUnitOfWork
        return await AsyncListCurrencies(uow)()
    dtos = run_ephemeral_async_uow(_logic)
    if json_output:
        payload = [
            {
                "code": c.code,
                "is_base": c.is_base,
                "exchange_rate": str(c.exchange_rate) if c.exchange_rate is not None else None,
            }
            for c in dtos
        ]
        print(json.dumps(payload))
        return
    for c in dtos:
        print(
            f"Currency {c.code} base={c.is_base} rate="
            f"{str(c.exchange_rate) if c.exchange_rate is not None else 'None'}"
        )


@currencies.command("add")
def currency_add(
    code: str,
    rate: str | None = Option(None, "--rate", help="Optional positive exchange rate (non-base only)."),
    json_output: bool = Option(False, "--json", help="Output JSON object for created/updated currency."),
) -> None:
    """Add a new currency or update its rate.

    Parameters:
        code: Currency code (upper normalized).
        rate: Optional exchange rate (>0) for non-base currency.
        json_output: When True prints JSON object {code,is_base,exchange_rate}; else human line.
    Errors:
        ValidationError on invalid code/rate/duplicate without rate; infra missing.
    """
    norm_code = code.strip().upper()
    if not norm_code:
        raise ValidationError("Empty currency code")

    async def _logic(uow):
        existing = await uow.currencies.get_by_code(norm_code)  # type: ignore[attr-defined]
        provided_rate: Decimal | None = None
        if rate is not None:
            try:
                provided_rate = Decimal(str(rate))
            except Exception as exc:  # pragma: no cover
                raise ValidationError("Invalid rate format") from exc
            if provided_rate <= 0:
                raise ValidationError("Rate must be > 0")
        if existing and provided_rate is None:
            raise ValidationError("Currency already exists")
        return await AsyncCreateCurrency(uow)(norm_code, provided_rate)

    dto = run_ephemeral_async_uow(_logic)
    if json_output:
        payload = {
            "code": dto.code,
            "is_base": dto.is_base,
            "exchange_rate": str(dto.exchange_rate) if dto.exchange_rate is not None else None,
        }
        print(json.dumps(payload))
        return
    print(
        f"Currency {dto.code} base={dto.is_base} rate="
        f"{str(dto.exchange_rate) if dto.exchange_rate is not None else 'None'}"
    )


@currencies.command("set-base")
def currency_set_base(
    code: str,
    json_output: bool = Option(False, "--json", help="Output JSON list after base switch."),
) -> None:
    """Set specified currency as the single base currency.

    Parameters:
        code: Target currency code (upper normalized).
        json_output: When True prints JSON list of currencies after base switch; else human lines.
    Behavior:
        Idempotent if already base. Base currency's exchange_rate becomes None.
    Errors:
        ValidationError if currency missing/invalid; infra missing.
    """
    norm_code = code.strip().upper()
    if not norm_code:
        raise ValidationError("Empty currency code")

    async def _logic(uow):
        # Verify exists first
        existing = await uow.currencies.get_by_code(norm_code)  # type: ignore[attr-defined]
        if not existing:
            raise ValidationError("Currency not found")
        await AsyncSetBaseCurrency(uow)(norm_code)
        return await AsyncListCurrencies(uow)()

    dtos = run_ephemeral_async_uow(_logic)
    if json_output:
        payload = [
            {
                "code": c.code,
                "is_base": c.is_base,
                "exchange_rate": str(c.exchange_rate) if c.exchange_rate is not None else None,
            }
            for c in dtos
        ]
        print(json.dumps(payload))
        return
    for c in dtos:
        print(
            f"Currency {c.code} base={c.is_base} rate="
            f"{str(c.exchange_rate) if c.exchange_rate is not None else 'None'}"
        )
