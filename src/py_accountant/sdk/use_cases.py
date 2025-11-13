"""Thin async facades over application use cases + SimpleTransactionParser.

This module provides small wrappers that translate SDK-friendly inputs into the
existing async use cases located in application.use_cases_async. No business
logic is duplicated here.

Public surface:
- SimpleTransactionParser: parse "SIDE:Account:Amount:Currency[:Rate]" into EntryLineDTO
- post_transaction(uow, lines, memo=None, meta=None) -> TransactionDTO
- get_account_balance(uow, account_full_name, as_of=None) -> Decimal
- get_ledger(uow, account_full_name, **kwargs) -> list[RichTransactionDTO]
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from application.dto.models import EntryLineDTO, RichTransactionDTO, TransactionDTO
from application.interfaces.ports import AsyncUnitOfWork, Clock
from application.use_cases_async.ledger import (
    AsyncGetAccountBalance,
    AsyncGetLedger,
    AsyncPostTransaction,
)

from .errors import UserInputError, map_exception

__all__ = [
    "SimpleTransactionParser",
    "post_transaction",
    "get_account_balance",
    "get_ledger",
]


@dataclass(slots=True)
class SimpleTransactionParser:
    """Parse a single entry line in format "SIDE:Account:Amount:Currency[:Rate]".

    Rules:
    - SIDE: one of {DEBIT, CREDIT} (case-insensitive), normalized to upper
    - Account: trimmed string; no further validation here
    - Amount: Decimal string > 0
    - Currency: trimmed A-Z, length 3..10, normalized to upper
    - Rate: optional Decimal > 0

    Returns EntryLineDTO with parsed values.
    Raises UserInputError on any format/validation issue.
    """

    def __call__(self, line: str) -> EntryLineDTO:
        if not isinstance(line, str):
            raise UserInputError("Line must be a string in format SIDE:Account:Amount:Currency[:Rate]")
        raw = line.strip()
        parts = raw.split(":")
        if len(parts) not in (4, 5) or any(p == "" for p in parts):
            raise UserInputError(
                "Invalid line format. Expected 'SIDE:Account:Amount:Currency[:Rate]'"
            )
        side_raw, account_raw, amount_raw, currency_raw, *rate_rest = parts
        side = side_raw.strip().upper()
        if side not in {"DEBIT", "CREDIT"}:
            raise UserInputError("SIDE must be DEBIT or CREDIT")
        account = account_raw.strip()
        if not account:
            raise UserInputError("Account must be non-empty")
        try:
            amount = Decimal(amount_raw.strip())
        except (InvalidOperation, ValueError):
            raise UserInputError("Amount must be a Decimal number")
        if amount <= Decimal("0"):
            raise UserInputError("Amount must be greater than 0")
        currency = currency_raw.strip().upper()
        if not (3 <= len(currency) <= 10) or not currency.isalpha():
            raise UserInputError("Currency must be A-Z with length 3..10")
        rate: Decimal | None = None
        if rate_rest:
            rate_str = rate_rest[0].strip()
            try:
                rate = Decimal(rate_str)
            except (InvalidOperation, ValueError):
                raise UserInputError("Rate must be a Decimal number if provided")
            if rate <= Decimal("0"):
                raise UserInputError("Rate must be greater than 0 if provided")
        return EntryLineDTO(
            side=side,
            account_full_name=account,
            amount=amount,
            currency_code=currency,
            exchange_rate=rate,
        )


async def post_transaction(
    uow: AsyncUnitOfWork,
    clock: Clock,
    lines: Iterable[EntryLineDTO | str],
    memo: str | None = None,
    meta: dict[str, Any] | None = None,
) -> TransactionDTO:
    """Post a transaction using AsyncPostTransaction use case.

    Accepts lines as EntryLineDTO objects or strings in the parser format.
    Converts strings via SimpleTransactionParser. Maps internal exceptions to
    public SDK errors.
    """
    try:
        parsed_lines: list[EntryLineDTO] = []
        parser = SimpleTransactionParser()
        for item in lines:
            if isinstance(item, EntryLineDTO):
                parsed_lines.append(item)
            elif isinstance(item, str):
                parsed_lines.append(parser(item))
            else:
                raise UserInputError("Each line must be EntryLineDTO or str in parser format")
        use_case = AsyncPostTransaction(uow=uow, clock=clock)
        return await use_case(parsed_lines, memo=memo, meta=meta)
    except Exception as exc:  # map to public errors
        raise map_exception(exc) from exc


async def get_account_balance(
    uow: AsyncUnitOfWork,
    clock: Clock,
    account_full_name: str,
    as_of: datetime | None = None,
) -> Decimal:
    """Return account balance via AsyncGetAccountBalance use case.

    Re-raises errors mapped to public SDK exceptions.
    """
    try:
        use_case = AsyncGetAccountBalance(uow=uow, clock=clock)
        return await use_case(account_full_name, as_of)
    except Exception as exc:  # map to public errors
        raise map_exception(exc) from exc


async def get_ledger(
    uow: AsyncUnitOfWork,
    clock: Clock,
    account_full_name: str,
    **kwargs: Any,
) -> list[RichTransactionDTO]:
    """Return ledger entries list via AsyncGetLedger use case.

    kwargs are passed through to the use case (start, end, meta, offset, limit, order).
    """
    try:
        use_case = AsyncGetLedger(uow=uow, clock=clock)
        return await use_case(account_full_name, **kwargs)
    except Exception as exc:  # map to public errors
        raise map_exception(exc) from exc
