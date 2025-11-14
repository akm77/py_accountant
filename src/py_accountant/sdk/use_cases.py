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
    - Account: trimmed string; may contain nested ':' segments (e.g. Assets:Cash:Wallet)
    - Amount: Decimal string > 0
    - Currency: trimmed A-Z, length 3..10, normalized to upper
    - Rate: optional Decimal > 0 (if present, it is the LAST token)

    Parsing strategy: right-to-left tail detection so Account may contain ':'
    segments. If the last token parses as Decimal (>0), it is treated as Rate;
    otherwise the last token is Currency and Rate is omitted.

    Returns EntryLineDTO with parsed values.
    Raises UserInputError on any format/validation issue.
    """

    def __call__(self, line: str) -> EntryLineDTO:
        if not isinstance(line, str):
            raise UserInputError("Line must be a string in format SIDE:Account:Amount:Currency[:Rate]")
        raw = line.strip()
        parts = raw.split(":")
        if len(parts) < 4 or any(p == "" for p in parts):
            raise UserInputError(
                "Invalid line format. Expected 'SIDE:Account:Amount:Currency[:Rate]'"
            )
        side_raw = parts[0]
        side = side_raw.strip().upper()
        if side not in {"DEBIT", "CREDIT"}:
            raise UserInputError("SIDE must be DEBIT or CREDIT")

        # Right-to-left parse: [SIDE][...ACCOUNT...][AMOUNT][CURRENCY][RATE?]
        tail = parts[1:]
        # Try to detect optional rate at the very end
        rate: Decimal | None = None
        maybe_rate_token = tail[-1].strip()
        try:
            candidate = Decimal(maybe_rate_token)
            if candidate > Decimal("0"):
                rate = candidate
                tail = tail[:-1]
            else:
                # Non-positive numbers are not valid rates; treat as currency token
                rate = None
        except (InvalidOperation, ValueError):
            rate = None
        if len(tail) < 2:
            raise UserInputError(
                "Invalid line format. Expected 'SIDE:Account:Amount:Currency[:Rate]'"
            )
        currency_raw = tail[-1].strip().upper()
        amount_raw = tail[-2].strip()
        account_tokens = tail[:-2]
        account = ":".join(t.strip() for t in account_tokens).strip()

        if not account:
            raise UserInputError("Account must be non-empty")
        try:
            amount = Decimal(amount_raw)
        except (InvalidOperation, ValueError) as err:
            raise UserInputError("Amount must be a Decimal number") from err
        if amount <= Decimal("0"):
            raise UserInputError("Amount must be greater than 0")
        if not (3 <= len(currency_raw) <= 10) or not currency_raw.isalpha():
            raise UserInputError("Currency must be A-Z with length 3..10")

        return EntryLineDTO(
            side=side,
            account_full_name=account,
            amount=amount,
            currency_code=currency_raw,
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

    This facade delegates to AsyncGetAccountBalance which implements a fast-path
    for current balance (as_of=None) by reading from the denormalized
    account_balances aggregate and falls back to a ledger scan for historical
    timestamps. Errors are mapped to public SDK exceptions.
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
