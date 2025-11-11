"""Telegram bot handlers (skeleton and iteration 3 parser + iteration 4 base commands).

Iteration 0: no real business logic. Future iterations will introduce async
parsers, validation, and integration with application use cases. This file
exists so that imports succeed early without pulling in domain/infrastructure
modules.

Iteration 3 expands this module with a pure parser for the /tx command
argument. It intentionally does not depend on aiogram or the project's
DTOs so it can be unit-tested in isolation.

Iteration 4 adds minimal async handlers for /start, /rates, /audit without
external framework dependencies. A very lean in-module router is provided
for later replacement by an aiogram Router. Handlers use an injected
AsyncUnitOfWork factory and Settings (set via register_handlers).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import cast

from application.dto.models import (
    CurrencyDTO,
    EntryLineDTO,  # Iteration 5 import
    ExchangeRateEventDTO,
)
from application.interfaces.ports import (
    AsyncUnitOfWork,
    Clock,  # Iteration 5 import
)
from application.use_cases_async.currencies import AsyncListCurrencies
from application.use_cases_async.fx_audit import AsyncListExchangeRateEvents
from application.use_cases_async.ledger import (  # Iteration 5 imports
    AsyncGetAccountBalance,
    AsyncPostTransaction,
)
from examples.telegram_bot.config import Settings
from infrastructure.persistence.inmemory.clock import SystemClock  # Iteration 5 import

# Public router placeholder replaced by a lean dict mapping command -> handler.
# Will be swapped for an aiogram Router in a later iteration without changing
# the public register_handlers API.
router: dict[str, Callable[..., Awaitable[str]]] = {}

# Internal DI storage (populated by register_handlers)
_uow_factory: Callable[[], AsyncUnitOfWork] | None = None
_settings: Settings | None = None
_clock: Clock | None = None  # Iteration 5 clock storage


class TxFormatError(Exception):
    """Raised when a transaction line in /tx payload fails validation.

    Public attributes:
    - line_index: int — zero-based index among non-empty lines in the payload.
    - reason: str — standardized reason code (e.g., 'invalid_side').
    - raw_line: str — the offending line (trimmed of surrounding whitespace).

    String form is: "line {line_index}: {reason}: {raw_line}".
    """

    def __init__(self, line_index: int, reason: str, raw_line: str) -> None:
        self.line_index = line_index
        self.reason = reason
        self.raw_line = raw_line
        super().__init__(str(self))

    def __str__(self) -> str:  # pragma: no cover - trivial formatting
        return f"line {self.line_index}: {self.reason}: {self.raw_line}"


@dataclass(slots=True)
class ParsedLine:
    """A single parsed line of the /tx payload.

    Fields:
    - side: 'DEBIT' | 'CREDIT' (uppercased)
    - account: original account string segment (outer whitespace trimmed).
      Nested names with ':' are preserved (no splitting beyond extraction).
    - amount: Decimal (> 0)
    - currency: str — ISO-like code uppercased, letters only, length 3..10
    - rate: Optional[Decimal] — None or Decimal (> 0) when provided
    """

    side: str
    account: str
    amount: Decimal
    currency: str
    rate: Decimal | None


def _is_valid_currency(code: str) -> bool:
    # Basic validation per spec: alpha-only, length 3..10
    return 3 <= len(code) <= 10 and code.isalpha()


def parse_tx_payload(raw: str) -> list[ParsedLine]:
    """Parse /tx payload into structured lines.

    The input format is a semicolon-separated list of lines, each in the form:
    SIDE:Account:Amount:Currency[:Rate]

    Rules and validation:
    - SIDE is DEBIT or CREDIT (case-insensitive; output uppercased)
    - Account is non-empty after trimming outer whitespace; nested ':' are kept
    - Amount parses to Decimal and must be > 0
    - Currency is letters-only (A-Z), length 3..10; output uppercased
    - Rate is optional; when present (as the last token) it parses to Decimal and must be > 0
    - Empty segments between semicolons (e.g., ";;" or trailing ";") are ignored

    This is a pure function: no logging and no external dependencies.

    Args:
        raw: The raw string following the /tx command.

    Returns:
        A list of ParsedLine objects. Returns an empty list if the payload
        contains only empty/whitespace segments.

    Raises:
        TxFormatError: on the first encountered validation error with details
        about the offending line.
    """

    if not raw:
        return []

    results: list[ParsedLine] = []
    # Split lines, trim, and skip empty ones; maintain index among non-empty
    segments = raw.split(";")
    non_empty: list[tuple[int, str]] = []
    for seg in segments:
        trimmed = seg.strip()
        if trimmed == "":
            continue
        non_empty.append((len(non_empty), trimmed))

    for line_index, line in non_empty:
        parts = [p.strip() for p in line.split(":")]
        if len(parts) < 4:
            raise TxFormatError(line_index, "invalid_parts_count", line)

        side = parts[0].upper()
        if side not in {"DEBIT", "CREDIT"}:
            raise TxFormatError(line_index, "invalid_side", line)

        # Determine presence of rate: only consider last token as rate when
        # there are at least 5 tokens and it parses as Decimal.
        rate: Decimal | None = None
        has_rate = False
        if len(parts) >= 5:
            try:
                rate_candidate = Decimal(parts[-1])
                rate = rate_candidate
                has_rate = True
            except (InvalidOperation, ValueError):
                # Not a valid Decimal -> it's part of account/currency, so no rate
                has_rate = False
                rate = None

        # Compute indices for amount and currency
        if has_rate:
            amount_token = parts[-3]
            currency_token = parts[-2]
            # account is everything between parts[1] and before amount
            account_tokens = parts[1:-3]
        else:
            amount_token = parts[-2]
            currency_token = parts[-1]
            account_tokens = parts[1:-2]

        account = ":".join(account_tokens).strip()
        if account == "":
            raise TxFormatError(line_index, "empty_account", line)

        # Parse amount
        try:
            amount = Decimal(amount_token)
        except (InvalidOperation, ValueError):
            raise TxFormatError(line_index, "invalid_amount", line) from None
        if amount <= 0:
            raise TxFormatError(line_index, "non_positive_amount", line)

        # Validate currency
        currency = currency_token.upper()
        if not _is_valid_currency(currency):
            raise TxFormatError(line_index, "invalid_currency", line)

        # Validate rate when present
        if has_rate:
            if rate is None:
                # Should not happen due to logic above, but keep for safety
                raise TxFormatError(line_index, "invalid_rate", line)
            if rate <= 0:
                raise TxFormatError(line_index, "non_positive_rate", line)

        results.append(
            ParsedLine(
                side=side,
                account=account,
                amount=amount,
                currency=currency,
                rate=rate if has_rate else None,
            )
        )

    return results


# ===================== Iteration 4: Basic async handlers =====================

def register_handlers(uow_factory: Callable[[], AsyncUnitOfWork], settings: Settings, clock: Clock | None = None) -> None:
    """Register base and extended command handlers into the global ``router``.

    Populates the module-level ``router`` dict mapping command names (without
    leading slash) to async handler functions. The provided ``uow_factory``,
    ``settings`` and optional ``clock`` are stored internally for subsequent
    handler calls.

    Backward compatibility:
    - Previous signature without ``clock`` still works because ``clock`` has a
      default of ``None``. When omitted, a ``SystemClock`` instance is created.

    Args:
        uow_factory: Callable returning a fresh ``AsyncUnitOfWork`` each call.
        settings: Loaded ``Settings`` with runtime configuration.
        clock: Optional time provider; defaults to ``SystemClock`` if ``None``.

    Returns:
        None. Mutates global ``router``.

    Notes:
        - Re-registering overwrites previous handlers and dependencies.
        - Keeps framework-agnostic design (simple dict) for aiogram integration later.
    """
    global _uow_factory, _settings, _clock, router
    _uow_factory = uow_factory
    _settings = settings
    _clock = clock if clock is not None else SystemClock()
    router.clear()
    router.update({
        "start": handle_start,
        "rates": handle_rates,
        "audit": handle_audit,
        "balance": handle_balance,  # Iteration 5
        "tx": handle_tx,            # Iteration 5
    })


async def handle_start(text: str | None = None) -> str:
    """Return a minimal help string listing available commands.

    Args:
        text: Optional raw text after command (ignored in this iteration).

    Returns:
        str: Short help line enumerating core commands.
    """
    # Static concise help; no UoW required.
    return "Commands: /start /rates /audit /balance /tx"


def _format_currency_line(dto: CurrencyDTO) -> str:
    """Format a single currency line for /rates output."""
    star = " *" if getattr(dto, "is_base", False) else ""
    rate = dto.exchange_rate if dto.exchange_rate is not None else "None"
    return f"{dto.code}{star} rate={rate}"


async def handle_rates(text: str | None = None) -> str:
    """Return human-readable list of currencies and rates.

    Args:
        text: Optional trailing text (unused).

    Returns:
        str: Multiline response or 'No currencies defined'.

    Error Handling:
        - ValueError from use case -> "Error: <message>".
        - Any other unexpected exception -> "Server error" (TODO: logging later).
    """
    factory_opt = _uow_factory
    if factory_opt is None:
        return "Server error"  # Not registered
    factory = cast(Callable[[], AsyncUnitOfWork], factory_opt)
    try:
        async with factory() as uow:
            items = await AsyncListCurrencies(uow)()
    except ValueError as e:  # domain-related validation surfaced as ValueError
        return f"Error: {e}"
    except Exception:  # pragma: no cover - defensive catch
        # TODO: log unexpected exception in iteration 7
        return "Server error"
    if not items:
        return "No currencies defined"
    lines = [_format_currency_line(c) for c in items]
    return "\n".join(lines)


def _format_audit_event(evt: ExchangeRateEventDTO) -> str:
    """Format a single FX audit event line for /audit output."""
    ts = evt.occurred_at.strftime('%Y-%m-%d %H:%M:%S')
    base = f"{ts} code={evt.code} rate={evt.rate} policy={evt.policy_applied}"
    if evt.source:
        base += f" source={evt.source}"
    return base


async def handle_audit(text: str | None = None) -> str:
    """Return recent FX exchange rate events limited by settings.audit_limit.

    Args:
        text: Optional trailing text (unused).

    Returns:
        str: Multiline response of events newest-first or 'No audit events'.

    Error Handling:
        - ValueError -> "Error: <message>".
        - Unexpected exception -> "Server error" (TODO: logging).
    """
    factory_opt = _uow_factory
    settings_opt = _settings
    if factory_opt is None or settings_opt is None:
        return "Server error"  # Not registered
    factory = cast(Callable[[], AsyncUnitOfWork], factory_opt)
    settings = cast(Settings, settings_opt)
    try:
        async with factory() as uow:
            # Request all events (None filters) then slice locally for clarity.
            events = await AsyncListExchangeRateEvents(uow)(None, None)
    except ValueError as e:
        return f"Error: {e}"
    except Exception:  # pragma: no cover - defensive catch
        # TODO: log unexpected exception in iteration 7
        return "Server error"
    if not events:
        return "No audit events"
    limit = settings.audit_limit
    if limit >= 0:
        events = events[:limit]
    lines = [_format_audit_event(evt) for evt in events]
    return "\n".join(lines)

# ===================== Iteration 5: /balance and /tx handlers =====================

def _format_balance_line(account_full_name: str, balance: Decimal) -> str:
    """Internal helper to format balance output (not exported)."""
    return f"{account_full_name} balance={balance}"  # Raw Decimal string per spec

async def handle_balance(text: str | None = None) -> str:
    """Return balance for a given account.

    Command format: /balance <Account:Full:Name>

    Args:
        text: Raw string after the command (may be None or empty).

    Returns:
        A single line '<full_name> balance=<DECIMAL>' or usage/error/server string.

    Errors:
        - Missing argument -> 'Usage: /balance <Account:Full:Name>'
        - ValueError from use case (invalid format / missing account) -> 'Error: <msg>'
        - Unexpected exception -> 'Server error' (TODO: logging in iteration 7)
    """
    factory_opt = _uow_factory
    clock_opt = _clock
    if factory_opt is None or clock_opt is None:
        return "Server error"  # Not registered
    account_name = (text or "").strip() if text is not None else ""
    if account_name == "":
        return "Usage: /balance <Account:Full:Name>"
    # Optional early format sanity: require at least one ':' as per ledger use case style
    if ":" not in account_name:
        # Let use case or repositories raise ValueError for consistency
        pass
    factory = cast(Callable[[], AsyncUnitOfWork], factory_opt)
    try:
        async with factory() as uow:
            bal = await AsyncGetAccountBalance(uow, clock_opt)(account_name)
    except ValueError as e:
        return f"Error: {e}"
    except Exception:  # pragma: no cover - defensive
        return "Server error"  # TODO: log later
    return _format_balance_line(account_name, bal)

async def handle_tx(text: str | None = None) -> str:
    """Parse transaction payload lines and persist a new transaction.

    Command format: /tx <payload>
    Payload format: SIDE:Account:Amount:Currency[:Rate];SIDE:... (semicolon separated)
    Uses ``parse_tx_payload`` to validate and parse each line, then maps to
    ``EntryLineDTO`` instances and calls ``AsyncPostTransaction``.

    Args:
        text: Raw payload string after the command (may be None or empty).

    Returns:
        'Transaction OK: <id> (<n> lines)' on success, or error classification.

    Errors:
        - TxFormatError -> 'Ошибка формата строки: line <i>: <reason>: <raw_line>'
        - Empty parsed lines -> 'Error: No lines'
        - ValueError from use case (missing account/currency/etc.) -> 'Error: <msg>'
        - Unexpected exception -> 'Server error' (TODO: logging)
    """
    factory_opt = _uow_factory
    clock_opt = _clock
    if factory_opt is None or clock_opt is None:
        return "Server error"  # Not registered
    payload = (text or "").strip()
    factory = cast(Callable[[], AsyncUnitOfWork], factory_opt)
    try:
        try:
            parsed = parse_tx_payload(payload)
        except TxFormatError as e:
            return f"Ошибка формата строки: {e}"  # e.__str__ already in required shape
        if not parsed:
            return "Error: No lines"
        lines: list[EntryLineDTO] = []
        for pl in parsed:
            lines.append(EntryLineDTO(
                side=pl.side,
                account_full_name=pl.account,
                amount=pl.amount,
                currency_code=pl.currency,
                exchange_rate=pl.rate,
                meta={},
            ))
        async with factory() as uow:
            tx = await AsyncPostTransaction(uow, clock_opt)(lines, memo=None, meta=None)
    except ValueError as e:
        return f"Error: {e}"
    except Exception:  # pragma: no cover - defensive
        return "Server error"  # TODO: log later
    return f"Transaction OK: {tx.id} ({len(tx.lines)} lines)"


__all__ = [
    "router",
    "TxFormatError",
    "ParsedLine",
    "parse_tx_payload",
    # Iteration 4 additions
    "register_handlers",
    "handle_start",
    "handle_rates",
    "handle_audit",
    # Iteration 5 additions
    "handle_balance",
    "handle_tx",
]
