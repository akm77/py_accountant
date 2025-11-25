# API Reference

> **Version**: 1.1.0-S4  
> **Date Updated**: 2025-11-25  
> **Status**: Async-first architecture

## Table of Contents

1. [Introduction](#introduction)
2. [Use Cases (Async)](#use-cases-async)
   - [Currencies Module](#currencies-module)
   - [Accounts Module](#accounts-module)
   - [Ledger Module](#ledger-module)
   - [Exchange Rate Events Module](#exchange-rate-events-module)
   - [FX Audit TTL Module](#fx-audit-ttl-module)
   - [Trading Balance Module](#trading-balance-module)
   - [Reporting Module](#reporting-module)
3. [Protocols (Ports)](#protocols-ports)
4. [Data Transfer Objects (DTOs)](#data-transfer-objects-dtos)
5. [Complete API Map](#complete-api-map)
6. [Migration Guide: Sync → Async](#migration-guide-sync--async)
7. [See Also](#see-also)

---

## Introduction

This document describes the public API of the py_accountant library for integrators. It provides comprehensive documentation of all use cases, protocols, and data transfer objects.

### Key Modules

- **`py_accountant.application.use_cases_async.*`** — Use cases (recommended, async-first)
- **`py_accountant.application.ports`** — Protocols for implementation by integrators
- **`py_accountant.application.dto`** — Data Transfer Objects
- **`py_accountant.infrastructure.persistence.sqlalchemy.*`** — Reference implementations

### Deprecated API

- **`py_accountant.application.use_cases.*`** (sync) — will be removed in v2.0.0

### Architecture Overview

py_accountant follows **Ports & Adapters (Hexagonal) architecture**:

- **Application Layer**: Contains use cases and defines ports (protocols)
- **Domain Layer**: Business logic and validation rules
- **Infrastructure Layer**: Concrete implementations of ports (repositories, UoW)

**Dependency Injection Pattern**: All use cases accept dependencies (repositories, UoW, clock) via constructor, allowing easy testing and custom implementations.

---

## Use Cases (Async)

Use cases implement application-level business logic by orchestrating domain objects and repositories. Each use case is a dataclass with a `__call__` method that executes the operation.

### General Pattern

All async use cases follow this pattern:

```python
from dataclasses import dataclass
from py_accountant.application.ports import AsyncUnitOfWork

@dataclass(slots=True)
class AsyncSomeUseCase:
    """Use case description."""
    
    uow: AsyncUnitOfWork
    # ... other dependencies
    
    async def __call__(self, param1: Type1, param2: Type2) -> ResultType:
        """Execute the use case.
        
        Args:
            param1: Description
            param2: Description
            
        Returns:
            ResultType description
            
        Raises:
            ValidationError: When domain validation fails
            ValueError: When resource not found
            DomainError: When business invariant violated
        """
        # Implementation
```

---

### Currencies Module

#### AsyncCreateCurrency

**Path**: `py_accountant.application.use_cases_async.currencies.AsyncCreateCurrency`

**Purpose**: Create or update a currency with domain validation.

**Signature**:
```python
async def __call__(
    self,
    code: str,
    exchange_rate: Decimal | None = None,
) -> CurrencyDTO
```

**Parameters**:
- `code` (str, required) — Currency code (ISO 4217 or custom). Must be 3-10 characters, will be normalized to uppercase.
- `exchange_rate` (Decimal | None, optional) — Exchange rate to base currency. Must be positive, quantized to 6 decimal places. Default: None.

**Returns**: `CurrencyDTO` — The created or updated currency.

**Raises**:
- `ValidationError` — Invalid code format (empty, too long/short, invalid characters) or non-positive exchange rate.
- No error on duplicate code — operation is idempotent, returns existing currency.

**Business Rules**:
1. Currency code validated and normalized via domain `Currency` entity (uppercase, length 3-10)
2. Exchange rate validated: must be positive, quantized to 6 decimal places
3. Base currency must have `exchange_rate=None` (invariant)
4. If currency exists and is base, provided rate is ignored
5. Repository remains CRUD-only; use case decides desired state

**Dependencies** (constructor injection):
- `uow: AsyncUnitOfWork` — Unit of Work for transaction management

**Example**:
```python
from decimal import Decimal
from py_accountant.application.use_cases_async.currencies import AsyncCreateCurrency
from py_accountant.infrastructure.persistence.sqlalchemy.uow import AsyncSqlAlchemyUnitOfWork
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

# Setup (typically in dependency injection container)
engine = create_async_engine("sqlite+aiosqlite:///accounting.db")
session_factory = async_sessionmaker(engine, expire_on_commit=False)
uow = AsyncSqlAlchemyUnitOfWork(session_factory)

# Create use case
create_currency = AsyncCreateCurrency(uow=uow)

# Execute
async with uow:
    usd = await create_currency(code="USD", exchange_rate=None)
    eur = await create_currency(code="EUR", exchange_rate=Decimal("0.85"))
    await uow.commit()

print(f"Created: {usd.code}")  # Created: USD
print(f"EUR rate: {eur.exchange_rate}")  # EUR rate: 0.850000
```

**See Also**:
- [AsyncSetBaseCurrency](#asyncsetbasecurrency) — Set a currency as base
- [AsyncListCurrencies](#asynclistcurrencies) — List all currencies
- [CurrencyDTO](#currencydto) — Currency data structure

---

#### AsyncSetBaseCurrency

**Path**: `py_accountant.application.use_cases_async.currencies.AsyncSetBaseCurrency`

**Purpose**: Select and persist a single base currency via domain rule.

**Signature**:
```python
async def __call__(self, code: str) -> None
```

**Parameters**:
- `code` (str, required) — Currency code to set as base (case-insensitive, will be normalized).

**Returns**: None

**Raises**:
- `ValidationError` — Currency code not found in the system.

**Business Rules**:
1. Uses `BaseCurrencyRule.ensure_single_base` to validate presence and mark only one base
2. Clears all existing base flags, then sets target as base
3. Base currency exchange rate is cleared (set to None)
4. Operation is idempotent (no error if already base)

**Dependencies** (constructor injection):
- `uow: AsyncUnitOfWork` — Unit of Work for transaction management

**Example**:
```python
from py_accountant.application.use_cases_async.currencies import (
    AsyncCreateCurrency,
    AsyncSetBaseCurrency,
)
from py_accountant.infrastructure.persistence.sqlalchemy.uow import AsyncSqlAlchemyUnitOfWork
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

# Setup
engine = create_async_engine("sqlite+aiosqlite:///accounting.db")
session_factory = async_sessionmaker(engine, expire_on_commit=False)
uow = AsyncSqlAlchemyUnitOfWork(session_factory)

create_currency = AsyncCreateCurrency(uow=uow)
set_base_currency = AsyncSetBaseCurrency(uow=uow)

# Execute
async with uow:
    # First create currency
    await create_currency(code="USD")
    # Then set as base
    await set_base_currency(code="USD")
    await uow.commit()

print("USD is now the base currency")
```

**See Also**:
- [AsyncCreateCurrency](#asynccreatecurrency) — Create currency first
- [BaseCurrencyRule](../src/py_accountant/domain/currencies.py) — Domain validation

---

#### AsyncListCurrencies

**Path**: `py_accountant.application.use_cases_async.currencies.AsyncListCurrencies`

**Purpose**: List all currencies as-is from repository (passthrough query).

**Signature**:
```python
async def __call__(self) -> list[CurrencyDTO]
```

**Parameters**: None

**Returns**: `list[CurrencyDTO]` — List of all currencies, possibly empty.

**Raises**: None

**Business Rules**:
- Simple passthrough to repository
- No filtering or sorting applied
- Returns empty list if no currencies exist

**Dependencies** (constructor injection):
- `uow: AsyncUnitOfWork` — Unit of Work for transaction management

**Example**:
```python
from py_accountant.application.use_cases_async.currencies import AsyncListCurrencies
from py_accountant.infrastructure.persistence.sqlalchemy.uow import AsyncSqlAlchemyUnitOfWork
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

# Setup
engine = create_async_engine("sqlite+aiosqlite:///accounting.db")
session_factory = async_sessionmaker(engine, expire_on_commit=False)
uow = AsyncSqlAlchemyUnitOfWork(session_factory)

list_currencies = AsyncListCurrencies(uow=uow)

# Execute
async with uow:
    currencies = await list_currencies()

print(f"Found {len(currencies)} currencies")
for cur in currencies:
    base_marker = " (base)" if cur.is_base else ""
    rate_str = f", rate={cur.exchange_rate}" if cur.exchange_rate else ""
    print(f"  - {cur.code}{base_marker}{rate_str}")
```

**See Also**:
- [AsyncCreateCurrency](#asynccreatecurrency) — Create currencies
- [CurrencyDTO](#currencydto) — Currency data structure

---

### Accounts Module

#### AsyncCreateAccount

**Path**: `py_accountant.application.use_cases_async.accounts.AsyncCreateAccount`

**Purpose**: Create a new account bound to an existing currency.

**Signature**:
```python
async def __call__(
    self,
    full_name: str,
    currency_code: str,
) -> AccountDTO
```

**Parameters**:
- `full_name` (str, required) — Hierarchical account path (e.g., "Assets:Cash", "Expenses:Food:Restaurants"). Whitespace is trimmed per segment.
- `currency_code` (str, required) — Currency code for the account (will be normalized to uppercase).

**Returns**: `AccountDTO` — The created account with generated ID.

**Raises**:
- `ValidationError` — Invalid `full_name` format (empty segments, bad delimiters) or invalid `currency_code` length.
- `ValueError` — Currency does not exist OR account with same `full_name` already exists.

**Business Rules**:
1. Account name validated via domain `Account` entity
2. Hierarchical naming: segments separated by `:`, each segment trimmed
3. Currency must exist before creating account
4. Account full_name must be unique across the system
5. Repository assigns unique ID

**Dependencies** (constructor injection):
- `uow: AsyncUnitOfWork` — Unit of Work for transaction management

**Example**:
```python
from py_accountant.application.use_cases_async.accounts import AsyncCreateAccount
from py_accountant.application.use_cases_async.currencies import AsyncCreateCurrency
from py_accountant.infrastructure.persistence.sqlalchemy.uow import AsyncSqlAlchemyUnitOfWork
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

# Setup
engine = create_async_engine("sqlite+aiosqlite:///accounting.db")
session_factory = async_sessionmaker(engine, expire_on_commit=False)
uow = AsyncSqlAlchemyUnitOfWork(session_factory)

create_currency = AsyncCreateCurrency(uow=uow)
create_account = AsyncCreateAccount(uow=uow)

# Execute
async with uow:
    # First ensure currency exists
    await create_currency(code="USD")
    
    # Create accounts
    cash = await create_account(
        full_name="Assets:Cash",
        currency_code="USD"
    )
    bank = await create_account(
        full_name="Assets:Bank:Checking",
        currency_code="USD"
    )
    
    await uow.commit()

print(f"Created account: {cash.full_name} ({cash.id})")
print(f"Created account: {bank.full_name} ({bank.id})")
```

**See Also**:
- [AsyncGetAccount](#asyncgetaccount) — Retrieve account by name
- [AsyncListAccounts](#asynclistaccounts) — List all accounts
- [AccountDTO](#accountdto) — Account data structure

---

#### AsyncGetAccount

**Path**: `py_accountant.application.use_cases_async.accounts.AsyncGetAccount`

**Purpose**: Fetch account by its full hierarchical name (passthrough query).

**Signature**:
```python
async def __call__(self, full_name: str) -> AccountDTO | None
```

**Parameters**:
- `full_name` (str, required) — Hierarchical account path (e.g., "Assets:Cash").

**Returns**: `AccountDTO | None` — The account if found, None otherwise.

**Raises**: None

**Business Rules**:
- Simple passthrough to repository
- No validation performed (repository performs exact match)
- Case-sensitive matching

**Dependencies** (constructor injection):
- `uow: AsyncUnitOfWork` — Unit of Work for transaction management

**Example**:
```python
from py_accountant.application.use_cases_async.accounts import AsyncGetAccount
from py_accountant.infrastructure.persistence.sqlalchemy.uow import AsyncSqlAlchemyUnitOfWork
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

# Setup
engine = create_async_engine("sqlite+aiosqlite:///accounting.db")
session_factory = async_sessionmaker(engine, expire_on_commit=False)
uow = AsyncSqlAlchemyUnitOfWork(session_factory)

get_account = AsyncGetAccount(uow=uow)

# Execute
async with uow:
    account = await get_account(full_name="Assets:Cash")

if account:
    print(f"Found: {account.full_name} (currency: {account.currency_code})")
else:
    print("Account not found")
```

**See Also**:
- [AsyncCreateAccount](#asynccreateaccount) — Create accounts
- [AsyncListAccounts](#asynclistaccounts) — List all accounts

---

#### AsyncListAccounts

**Path**: `py_accountant.application.use_cases_async.accounts.AsyncListAccounts`

**Purpose**: List all accounts (passthrough query).

**Signature**:
```python
async def __call__(self) -> list[AccountDTO]
```

**Parameters**: None

**Returns**: `list[AccountDTO]` — List of all accounts, possibly empty.

**Raises**: None

**Business Rules**:
- Simple passthrough to repository
- No filtering or sorting applied
- Returns empty list if no accounts exist

**Dependencies** (constructor injection):
- `uow: AsyncUnitOfWork` — Unit of Work for transaction management

**Example**:
```python
from py_accountant.application.use_cases_async.accounts import AsyncListAccounts
from py_accountant.infrastructure.persistence.sqlalchemy.uow import AsyncSqlAlchemyUnitOfWork
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

# Setup
engine = create_async_engine("sqlite+aiosqlite:///accounting.db")
session_factory = async_sessionmaker(engine, expire_on_commit=False)
uow = AsyncSqlAlchemyUnitOfWork(session_factory)

list_accounts = AsyncListAccounts(uow=uow)

# Execute
async with uow:
    accounts = await list_accounts()

print(f"Found {len(accounts)} accounts")
for acc in accounts:
    print(f"  - {acc.full_name} ({acc.currency_code})")
```

**See Also**:
- [AsyncCreateAccount](#asynccreateaccount) — Create accounts
- [AccountDTO](#accountdto) — Account data structure

---

### Ledger Module

#### AsyncPostTransaction

**Path**: `py_accountant.application.use_cases_async.ledger.AsyncPostTransaction`

**Purpose**: Persist a financial transaction after domain ledger balance validation.

**Signature**:
```python
async def __call__(
    self,
    lines: list[EntryLineDTO],
    memo: str | None = None,
    meta: dict[str, Any] | None = None,
) -> TransactionDTO
```

**Parameters**:
- `lines` (list[EntryLineDTO], required) — Transaction lines (debit/credit entries). Must contain at least one line.
- `memo` (str | None, optional) — Transaction description/note. Default: None.
- `meta` (dict[str, Any] | None, optional) — Additional metadata as key-value pairs. Default: None (empty dict).

**Returns**: `TransactionDTO` — The persisted transaction with generated ID and timestamp.

**Raises**:
- `ValidationError` — Empty lines list, invalid side ("DEBIT"/"CREDIT"), non-positive amount, bad currency code length, absent base currency, unknown currency, missing/non-positive rate for non-base currency.
- `DomainError` — Ledger not balanced after conversion to base currency and quantization.
- `ValueError` — Account or currency not found in the system (resource missing).

**Business Rules**:
1. At least one line required
2. All accounts and currencies must exist before posting
3. Each line validated via domain `LedgerEntry` (side, amount > 0, currency code format)
4. All currencies projected to domain `Currency` objects for validation
5. `LedgerValidator.validate()` ensures:
   - Base currency exists
   - All referenced currencies exist
   - Non-base currencies have positive rates
   - Debit/Credit balanced after conversion to base currency (money quantization applied)
6. Transaction ID auto-generated: `tx:<uuid>`
7. Timestamp auto-generated: `clock.now()`

**Dependencies** (constructor injection):
- `uow: AsyncUnitOfWork` — Unit of Work for transaction management
- `clock: Clock` — Time provider for timestamp generation

**Example**:
```python
from decimal import Decimal
from py_accountant.application.use_cases_async.ledger import AsyncPostTransaction
from py_accountant.application.dto.models import EntryLineDTO
from py_accountant.infrastructure.persistence.sqlalchemy.uow import AsyncSqlAlchemyUnitOfWork
from py_accountant.infrastructure.persistence.inmemory.clock import SystemClock
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

# Setup
engine = create_async_engine("sqlite+aiosqlite:///accounting.db")
session_factory = async_sessionmaker(engine, expire_on_commit=False)
uow = AsyncSqlAlchemyUnitOfWork(session_factory)
clock = SystemClock()

post_transaction = AsyncPostTransaction(uow=uow, clock=clock)

# Prepare transaction lines
lines = [
    EntryLineDTO(
        side="DEBIT",
        account_full_name="Assets:Cash",
        amount=Decimal("100.00"),
        currency_code="USD",
    ),
    EntryLineDTO(
        side="CREDIT",
        account_full_name="Income:Salary",
        amount=Decimal("100.00"),
        currency_code="USD",
    ),
]

# Execute
async with uow:
    tx = await post_transaction(
        lines=lines,
        memo="Salary payment",
        meta={"source": "payroll", "employee_id": "E123"}
    )
    await uow.commit()

print(f"Transaction posted: {tx.id}")
print(f"Occurred at: {tx.occurred_at}")
print(f"Memo: {tx.memo}")
```

**Multi-Currency Example**:
```python
from decimal import Decimal
from py_accountant.application.dto.models import EntryLineDTO

# Assuming USD is base currency, EUR has rate 0.85
lines = [
    EntryLineDTO(
        side="DEBIT",
        account_full_name="Assets:Cash:EUR",
        amount=Decimal("100.00"),
        currency_code="EUR",
        exchange_rate=Decimal("0.85"),  # Optional: will be fetched from currency if None
    ),
    EntryLineDTO(
        side="CREDIT",
        account_full_name="Assets:Cash:USD",
        amount=Decimal("85.00"),
        currency_code="USD",
    ),
]

async with uow:
    tx = await post_transaction(lines=lines, memo="Currency exchange")
    await uow.commit()
```

**See Also**:
- [AsyncGetLedger](#asyncgetledger) — Query ledger entries
- [AsyncListTransactionsBetween](#asynclisttransactionsbetween) — Query transactions by time range
- [TransactionDTO](#transactiondto) — Transaction data structure
- [EntryLineDTO](#entrylinedto) — Transaction line structure

---

#### AsyncListTransactionsBetween

**Path**: `py_accountant.application.use_cases_async.ledger.AsyncListTransactionsBetween`

**Purpose**: List transactions between start and end timestamps (inclusive boundaries).

**Signature**:
```python
async def __call__(
    self,
    start: datetime,
    end: datetime,
    meta: dict[str, Any] | None = None,
) -> list[TransactionDTO]
```

**Parameters**:
- `start` (datetime, required) — Start timestamp (inclusive). Must be timezone-aware.
- `end` (datetime, required) — End timestamp (inclusive). Must be timezone-aware.
- `meta` (dict[str, Any] | None, optional) — Metadata filter; all key/value pairs must match exactly. Default: None (no filter).

**Returns**: `list[TransactionDTO]` — Transactions ordered ascending by `occurred_at`.

**Raises**:
- `ValueError` — If `start > end`.

**Business Rules**:
- Time range is inclusive on both ends
- Results ordered by `occurred_at` ascending
- Empty or None `meta` dict returns unfiltered results
- Meta matching is exact (all provided keys must match exactly)

**Dependencies** (constructor injection):
- `uow: AsyncUnitOfWork` — Unit of Work for transaction management

**Example**:
```python
from datetime import datetime, UTC, timedelta
from py_accountant.application.use_cases_async.ledger import AsyncListTransactionsBetween
from py_accountant.infrastructure.persistence.sqlalchemy.uow import AsyncSqlAlchemyUnitOfWork
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

# Setup
engine = create_async_engine("sqlite+aiosqlite:///accounting.db")
session_factory = async_sessionmaker(engine, expire_on_commit=False)
uow = AsyncSqlAlchemyUnitOfWork(session_factory)

list_txs = AsyncListTransactionsBetween(uow=uow)

# Query last 7 days
now = datetime.now(UTC)
start = now - timedelta(days=7)

async with uow:
    transactions = await list_txs(start=start, end=now)

print(f"Found {len(transactions)} transactions in last 7 days")
for tx in transactions:
    print(f"  {tx.occurred_at}: {tx.memo} ({len(tx.lines)} lines)")
```

**With Metadata Filter**:
```python
# Query transactions from specific source
async with uow:
    payroll_txs = await list_txs(
        start=start,
        end=now,
        meta={"source": "payroll"}
    )

print(f"Found {len(payroll_txs)} payroll transactions")
```

**See Also**:
- [AsyncPostTransaction](#asyncposttransaction) — Create transactions
- [AsyncGetLedger](#asyncgetledger) — Query account-specific ledger
- [TransactionDTO](#transactiondto) — Transaction data structure

---

#### AsyncGetLedger

**Path**: `py_accountant.application.use_cases_async.ledger.AsyncGetLedger`

**Purpose**: Return ledger entries for a specific account with pagination, ordering, and metadata filtering.

**Signature**:
```python
async def __call__(
    self,
    account_full_name: str,
    start: datetime | None = None,
    end: datetime | None = None,
    meta: dict[str, Any] | None = None,
    *,
    offset: int = 0,
    limit: int | None = None,
    order: str = "ASC",
) -> list[RichTransactionDTO]
```

**Parameters**:
- `account_full_name` (str, required) — Full hierarchical account name (e.g., "Assets:Cash").
- `start` (datetime | None, optional) — Start timestamp (inclusive). Default: epoch with same timezone as `clock.now()`.
- `end` (datetime | None, optional) — End timestamp (inclusive). Default: `clock.now()`.
- `meta` (dict[str, Any] | None, optional) — Metadata filter (exact match). Default: None.
- `offset` (int, keyword-only, optional) — Pagination offset (0-based). Negative values return empty list. Default: 0.
- `limit` (int | None, keyword-only, optional) — Maximum results to return. Values ≤ 0 return empty list. Default: None (no limit).
- `order` (str, keyword-only, optional) — Sort order: "ASC" or "DESC" by `occurred_at`. Default: "ASC".

**Returns**: `list[RichTransactionDTO]` — Ledger entries for the account.

**Raises**:
- `ValueError` — Invalid `account_full_name` format (missing `:`), `start > end`, invalid `order` (not "ASC"/"DESC").

**Business Rules**:
- Account name must contain at least one `:` separator
- Time range defaults: start=epoch, end=now
- Pagination: negative offset or non-positive limit returns empty list
- Ordering case-insensitive ("asc"/"ASC", "desc"/"DESC")
- Returns only transactions affecting the specified account

**Dependencies** (constructor injection):
- `uow: AsyncUnitOfWork` — Unit of Work for transaction management
- `clock: Clock` — Time provider for default timestamps

**Example**:
```python
from datetime import datetime, UTC
from py_accountant.application.use_cases_async.ledger import AsyncGetLedger
from py_accountant.infrastructure.persistence.sqlalchemy.uow import AsyncSqlAlchemyUnitOfWork
from py_accountant.infrastructure.persistence.inmemory.clock import SystemClock
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

# Setup
engine = create_async_engine("sqlite+aiosqlite:///accounting.db")
session_factory = async_sessionmaker(engine, expire_on_commit=False)
uow = AsyncSqlAlchemyUnitOfWork(session_factory)
clock = SystemClock()

get_ledger = AsyncGetLedger(uow=uow, clock=clock)

# Query ledger for account
async with uow:
    entries = await get_ledger(
        account_full_name="Assets:Cash",
        order="DESC",
        limit=10
    )

print(f"Last 10 transactions for Assets:Cash:")
for entry in entries:
    print(f"  {entry.occurred_at}: {entry.memo}")
    for line in entry.lines:
        if line.account_full_name == "Assets:Cash":
            print(f"    {line.side}: {line.amount} {line.currency_code}")
```

**Pagination Example**:
```python
# Get page 2 (skip first 20, get next 20)
async with uow:
    page2 = await get_ledger(
        account_full_name="Assets:Bank:Checking",
        offset=20,
        limit=20,
        order="DESC"
    )
```

**See Also**:
- [AsyncPostTransaction](#asyncposttransaction) — Create transactions
- [AsyncListTransactionsBetween](#asynclisttransactionsbetween) — Query all transactions
- [RichTransactionDTO](#richtransactiondto) — Ledger entry structure

---

### Exchange Rate Events Module

#### AsyncAddExchangeRateEvent

**Path**: `py_accountant.application.use_cases_async.fx_audit.AsyncAddExchangeRateEvent`

**Purpose**: Append an FX exchange rate event to the audit log (append-only).

**Signature**:
```python
async def __call__(
    self,
    code: str,
    rate: Decimal,
    occurred_at: datetime,
    policy_applied: str,
    source: str | None = None,
) -> ExchangeRateEventDTO
```

**Parameters**:
- `code` (str, required) — Currency code affected.
- `rate` (Decimal, required) — Effective exchange rate applied.
- `occurred_at` (datetime, required) — Timestamp of event occurrence (timezone-aware).
- `policy_applied` (str, required) — Description or key of policy applied (e.g., "manual", "auto-fetch", "batch-update").
- `source` (str | None, optional) — External source tag (e.g., "ECB", "manual-entry"). Default: None.

**Returns**: `ExchangeRateEventDTO` — The inserted event with generated ID.

**Raises**:
- `ValueError` — If repository validates and rejects data (e.g., missing/invalid code format).

**Business Rules**:
- Events are append-only (no updates/deletes via this use case)
- No deduplication performed
- Audit trail for compliance and debugging

**Dependencies** (constructor injection):
- `uow: AsyncUnitOfWork` — Unit of Work for transaction management

**Example**:
```python
from decimal import Decimal
from datetime import datetime, UTC
from py_accountant.application.use_cases_async.fx_audit import AsyncAddExchangeRateEvent
from py_accountant.infrastructure.persistence.sqlalchemy.uow import AsyncSqlAlchemyUnitOfWork
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

# Setup
engine = create_async_engine("sqlite+aiosqlite:///accounting.db")
session_factory = async_sessionmaker(engine, expire_on_commit=False)
uow = AsyncSqlAlchemyUnitOfWork(session_factory)

add_event = AsyncAddExchangeRateEvent(uow=uow)

# Log rate update
async with uow:
    event = await add_event(
        code="EUR",
        rate=Decimal("0.85"),
        occurred_at=datetime.now(UTC),
        policy_applied="manual-update",
        source="admin-panel"
    )
    await uow.commit()

print(f"Event logged: {event.id}, rate={event.rate}")
```

**See Also**:
- [AsyncListExchangeRateEvents](#asynclistexchangerateevents) — Query events
- [ExchangeRateEventDTO](#exchangerateeventdto) — Event data structure

---

#### AsyncListExchangeRateEvents

**Path**: `py_accountant.application.use_cases_async.fx_audit.AsyncListExchangeRateEvents`

**Purpose**: List recent FX exchange rate events with optional filtering.

**Signature**:
```python
async def __call__(
    self,
    code: str | None = None,
    limit: int | None = None,
) -> list[ExchangeRateEventDTO]
```

**Parameters**:
- `code` (str | None, optional) — Currency code filter. If None, returns events for all currencies. Default: None.
- `limit` (int | None, optional) — Maximum number of events to return. Negative values return empty list. Default: None (no limit).

**Returns**: `list[ExchangeRateEventDTO]` — Events ordered newest-first.

**Raises**: None

**Business Rules**:
- Results ordered by `occurred_at` descending (newest first)
- Negative limit returns empty list
- No pagination (use limit for simple truncation)

**Dependencies** (constructor injection):
- `uow: AsyncUnitOfWork` — Unit of Work for transaction management

**Example**:
```python
from py_accountant.application.use_cases_async.fx_audit import AsyncListExchangeRateEvents
from py_accountant.infrastructure.persistence.sqlalchemy.uow import AsyncSqlAlchemyUnitOfWork
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

# Setup
engine = create_async_engine("sqlite+aiosqlite:///accounting.db")
session_factory = async_sessionmaker(engine, expire_on_commit=False)
uow = AsyncSqlAlchemyUnitOfWork(session_factory)

list_events = AsyncListExchangeRateEvents(uow=uow)

# Get last 10 EUR events
async with uow:
    eur_events = await list_events(code="EUR", limit=10)

print(f"Last {len(eur_events)} EUR rate events:")
for event in eur_events:
    print(f"  {event.occurred_at}: rate={event.rate} ({event.policy_applied})")
```

**See Also**:
- [AsyncAddExchangeRateEvent](#asyncaddexchangerateevent) — Create events
- [ExchangeRateEventDTO](#exchangerateeventdto) — Event data structure

---

### FX Audit TTL Module

#### AsyncPlanFxAuditTTL

**Path**: `py_accountant.application.use_cases_async.fx_audit_ttl.AsyncPlanFxAuditTTL`

**Purpose**: Compute FX audit TTL (Time-To-Live) plan: cutoff timestamp, candidate event IDs, and batch windows for deletion/archival.

**Signature**:
```python
async def __call__(
    self,
    retention_days: int,
    batch_size: int,
    mode: str = "none",
    limit: int | None = None,
    dry_run: bool = False,
) -> FxAuditTTLPlanDTO
```

**Parameters**:
- `retention_days` (int, required) — Non-negative retention window in days. 0 means cutoff = now.
- `batch_size` (int, required) — Positive batch size for processing (must be > 0).
- `mode` (str, optional) — Operation mode: "none", "delete", or "archive" (case-insensitive). Default: "none".
- `limit` (int | None, optional) — Optional cap on number of old event IDs captured in plan. Default: None (no limit, up to 100,000 safety cap).
- `dry_run` (bool, optional) — If True, execution will report 0 side effects. Default: False.

**Returns**: `FxAuditTTLPlanDTO` — Plan describing cutoff, batching strategy, and candidate event IDs.

**Raises**:
- `ValidationError` — Invalid arguments: negative `retention_days`, non-positive `batch_size`, invalid `mode`, negative `limit`.
- `ValueError` — Missing repository (unlikely misconfiguration).

**Business Rules**:
1. Cutoff = `clock.now() - timedelta(days=retention_days)`
2. Scans events older than cutoff (up to 100,000 safety cap)
3. Generates batch windows: `[(offset=0, limit=batch_size), (offset=batch_size, limit=batch_size), ...]`
4. Mode determines execution behavior:
   - "none": no-op (plan only)
   - "delete": delete old events
   - "archive": archive then delete
5. Dry-run mode: plan created but execution reports zero effects

**Dependencies** (constructor injection):
- `uow: AsyncUnitOfWork` — Unit of Work for transaction management
- `clock: Clock` — Time provider for cutoff calculation

**Example**:
```python
from py_accountant.application.use_cases_async.fx_audit_ttl import AsyncPlanFxAuditTTL
from py_accountant.infrastructure.persistence.sqlalchemy.uow import AsyncSqlAlchemyUnitOfWork
from py_accountant.infrastructure.persistence.inmemory.clock import SystemClock
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

# Setup
engine = create_async_engine("sqlite+aiosqlite:///accounting.db")
session_factory = async_sessionmaker(engine, expire_on_commit=False)
uow = AsyncSqlAlchemyUnitOfWork(session_factory)
clock = SystemClock()

plan_ttl = AsyncPlanFxAuditTTL(uow=uow, clock=clock)

# Plan deletion of events older than 90 days
async with uow:
    plan = await plan_ttl(
        retention_days=90,
        batch_size=1000,
        mode="delete",
        dry_run=True  # Preview only
    )

print(f"TTL Plan:")
print(f"  Cutoff: {plan.cutoff}")
print(f"  Mode: {plan.mode}")
print(f"  Total old events: {plan.total_old}")
print(f"  Batches: {len(plan.batches)}")
print(f"  Candidate IDs: {len(plan.old_event_ids)}")
```

**See Also**:
- [AsyncExecuteFxAuditTTL](#asyncexecutefxauditttl) — Execute the plan
- [FxAuditTTLPlanDTO](#fxauditttlplandto) — Plan data structure

---

#### AsyncExecuteFxAuditTTL

**Path**: `py_accountant.application.use_cases_async.fx_audit_ttl.AsyncExecuteFxAuditTTL`

**Purpose**: Execute a previously computed TTL plan: archive/delete events or no-op/dry-run.

**Signature**:
```python
async def __call__(self, plan: FxAuditTTLPlanDTO) -> FxAuditTTLResultDTO
```

**Parameters**:
- `plan` (FxAuditTTLPlanDTO, required) — Plan produced by `AsyncPlanFxAuditTTL`.

**Returns**: `FxAuditTTLResultDTO` — Execution result summary.

**Raises**:
- `ValidationError` — Plan inconsistent: invalid mode, empty IDs with delete/archive mode, batch coverage mismatch, empty batch slices.
- `ValueError` — Missing repository.

**Business Rules**:
1. **Dry-run or mode "none"**: Returns zero counts, no side effects
2. **Mode "delete"**: Deletes events by ID per batch
3. **Mode "archive"**: Archives then deletes (two-phase) per batch
4. Processes batches sequentially
5. Result summarizes: mode, archived count, deleted count, batches executed

**Dependencies** (constructor injection):
- `uow: AsyncUnitOfWork` — Unit of Work for transaction management
- `clock: Clock` — Time provider for archive timestamp

**Example**:
```python
from py_accountant.application.use_cases_async.fx_audit_ttl import (
    AsyncPlanFxAuditTTL,
    AsyncExecuteFxAuditTTL,
)
from py_accountant.infrastructure.persistence.sqlalchemy.uow import AsyncSqlAlchemyUnitOfWork
from py_accountant.infrastructure.persistence.inmemory.clock import SystemClock
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

# Setup
engine = create_async_engine("sqlite+aiosqlite:///accounting.db")
session_factory = async_sessionmaker(engine, expire_on_commit=False)
uow = AsyncSqlAlchemyUnitOfWork(session_factory)
clock = SystemClock()

plan_ttl = AsyncPlanFxAuditTTL(uow=uow, clock=clock)
execute_ttl = AsyncExecuteFxAuditTTL(uow=uow, clock=clock)

# Plan and execute archive
async with uow:
    # First, create plan
    plan = await plan_ttl(
        retention_days=90,
        batch_size=1000,
        mode="archive",
        dry_run=False
    )
    
    # Then execute
    result = await execute_ttl(plan=plan)
    await uow.commit()

print(f"TTL Execution Result:")
print(f"  Mode: {result.executed_mode}")
print(f"  Archived: {result.archived_count}")
print(f"  Deleted: {result.deleted_count}")
print(f"  Batches: {result.batches_executed}")
```

**See Also**:
- [AsyncPlanFxAuditTTL](#asyncplanfxauditttl) — Create plan
- [FxAuditTTLResultDTO](#fxauditttlresultdto) — Result data structure

---

### Trading Balance Module

#### AsyncGetTradingBalanceRaw

**Path**: `py_accountant.application.use_cases_async.trading_balance.AsyncGetTradingBalanceRaw`

**Purpose**: Compute raw (non-converted) trading balance within a time window, aggregated by currency.

**Signature**:
```python
async def __call__(
    self,
    *,
    start: datetime | None = None,
    end: datetime | None = None,
    meta: dict[str, Any] | None = None,
) -> list[TradingBalanceLineSimple]
```

**Parameters** (all keyword-only):
- `start` (datetime | None, optional) — Inclusive window start. Default: epoch with timezone of `clock.now()`.
- `end` (datetime | None, optional) — Inclusive window end. Default: `clock.now()`.
- `meta` (dict[str, Any] | None, optional) — Metadata filter (exact match). Default: None.

**Returns**: `list[TradingBalanceLineSimple]` — Raw balance lines sorted by currency code, possibly empty.

**Raises**:
- `ValueError` — Invalid window (`start > end`) or `meta` not dict/None.
- `ValidationError` — Domain validation issues (invalid ledger entry: side, amount, currency code).

**Business Rules**:
1. Aggregates debit/credit per currency using domain `RawAggregator`
2. No conversion to base currency (raw amounts)
3. Net = Debit - Credit
4. Results sorted by currency code ascending
5. Repository remains CRUD-only

**Dependencies** (constructor injection):
- `uow: AsyncUnitOfWork` — Unit of Work for transaction management
- `clock: Clock` — Time provider for default timestamps

**Example**:
```python
from py_accountant.application.use_cases_async.trading_balance import AsyncGetTradingBalanceRaw
from py_accountant.infrastructure.persistence.sqlalchemy.uow import AsyncSqlAlchemyUnitOfWork
from py_accountant.infrastructure.persistence.inmemory.clock import SystemClock
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

# Setup
engine = create_async_engine("sqlite+aiosqlite:///accounting.db")
session_factory = async_sessionmaker(engine, expire_on_commit=False)
uow = AsyncSqlAlchemyUnitOfWork(session_factory)
clock = SystemClock()

get_balance = AsyncGetTradingBalanceRaw(uow=uow, clock=clock)

# Get raw balance for all time
async with uow:
    lines = await get_balance()

print("Raw Trading Balance:")
for line in lines:
    print(f"  {line.currency_code}:")
    print(f"    Debit:  {line.debit}")
    print(f"    Credit: {line.credit}")
    print(f"    Net:    {line.net}")
```

**See Also**:
- [AsyncGetTradingBalanceDetailed](#asyncgettradingbalancedetailed) — With base currency conversion
- [TradingBalanceLineSimple](#tradingbalancelinesimple) — Raw balance line structure

---

#### AsyncGetTradingBalanceDetailed

**Path**: `py_accountant.application.use_cases_async.trading_balance.AsyncGetTradingBalanceDetailed`

**Purpose**: Compute detailed trading balance with conversion to base currency.

**Signature**:
```python
async def __call__(
    self,
    *,
    start: datetime | None = None,
    end: datetime | None = None,
    meta: dict[str, Any] | None = None,
    base_currency: str | None = None,
) -> list[TradingBalanceLineDetailed]
```

**Parameters** (all keyword-only):
- `start` (datetime | None, optional) — Inclusive window start. Default: epoch with timezone of `clock.now()`.
- `end` (datetime | None, optional) — Inclusive window end. Default: `clock.now()`.
- `meta` (dict[str, Any] | None, optional) — Metadata filter (exact match). Default: None.
- `base_currency` (str | None, optional) — Explicit base currency code. If None, inferred from repository. Default: None.

**Returns**: `list[TradingBalanceLineDetailed]` — Detailed balance lines with base conversions, sorted by currency code.

**Raises**:
- `ValueError` — Invalid window (`start > end`) or `meta` not dict/None.
- `ValidationError` — Domain validation issues: invalid ledger entry, base currency not found/not defined, unknown currency, missing/non-positive rate for non-base currency.

**Business Rules**:
1. Uses domain `ConvertedAggregator` to aggregate and convert to base
2. Base currency can be explicit or inferred (detected via domain helper)
3. Each line includes:
   - Raw amounts (debit, credit, net) in original currency
   - Used exchange rate (normalized to 6 decimal places)
   - Converted amounts (debit_base, credit_base, net_base) in base currency
4. Results sorted by currency code ascending
5. Base currency validation happens early (even if no transactions)

**Dependencies** (constructor injection):
- `uow: AsyncUnitOfWork` — Unit of Work for transaction management
- `clock: Clock` — Time provider for default timestamps

**Example**:
```python
from py_accountant.application.use_cases_async.trading_balance import AsyncGetTradingBalanceDetailed
from py_accountant.infrastructure.persistence.sqlalchemy.uow import AsyncSqlAlchemyUnitOfWork
from py_accountant.infrastructure.persistence.inmemory.clock import SystemClock
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

# Setup
engine = create_async_engine("sqlite+aiosqlite:///accounting.db")
session_factory = async_sessionmaker(engine, expire_on_commit=False)
uow = AsyncSqlAlchemyUnitOfWork(session_factory)
clock = SystemClock()

get_balance = AsyncGetTradingBalanceDetailed(uow=uow, clock=clock)

# Get detailed balance (base currency auto-detected)
async with uow:
    lines = await get_balance()

print("Detailed Trading Balance:")
for line in lines:
    print(f"  {line.currency_code} (rate: {line.used_rate}):")
    print(f"    Raw:  Debit={line.debit}, Credit={line.credit}, Net={line.net}")
    print(f"    Base: Debit={line.debit_base}, Credit={line.credit_base}, Net={line.net_base} {line.base_currency_code}")
```

**With Explicit Base Currency**:
```python
async with uow:
    lines = await get_balance(base_currency="USD")
```

**See Also**:
- [AsyncGetTradingBalanceRaw](#asyncgettradingbalanceraw) — Without conversion
- [TradingBalanceLineDetailed](#tradingbalancelinedetailed) — Detailed balance line structure

---

### Reporting Module

#### AsyncGetParityReport

**Path**: `py_accountant.application.use_cases_async.reporting.AsyncGetParityReport`

**Purpose**: Build a parity report snapshot for selected currencies with optional deviation analysis.

**Signature**:
```python
async def __call__(
    self,
    *,
    base_only: bool = False,
    codes: list[str] | None = None,
    include_dev: bool = True,
) -> ParityReportDTO
```

**Parameters** (all keyword-only):
- `base_only` (bool, optional) — If True, include only the base currency. Default: False.
- `codes` (list[str] | None, optional) — Currency codes to filter (case-insensitive, duplicates trimmed). Invalid/empty codes ignored. Default: None (all currencies).
- `include_dev` (bool, optional) — If True and base exists, compute `deviation_pct` heuristic for non-base currencies. Default: True.

**Returns**: `ParityReportDTO` — Report with lines, base currency, and deviation flag.

**Raises**:
- `ValidationError` — If `codes` is not a list or None.

**Business Rules**:
1. Deviation heuristic: `(latest_rate - 1) * 100` where base parity is 1.0
2. Base currency has `latest_rate=None`, `deviation_pct=None`
3. If `base_only=True`, returns only base currency (if exists and passes filter)
4. Lines sorted by currency code ascending
5. `has_deviation=True` if any line has non-None deviation

**Dependencies** (constructor injection):
- `uow: AsyncUnitOfWork` — Unit of Work for transaction management
- `clock: Clock` — Time provider for report timestamp

**Example**:
```python
from py_accountant.application.use_cases_async.reporting import AsyncGetParityReport
from py_accountant.infrastructure.persistence.sqlalchemy.uow import AsyncSqlAlchemyUnitOfWork
from py_accountant.infrastructure.persistence.inmemory.clock import SystemClock
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

# Setup
engine = create_async_engine("sqlite+aiosqlite:///accounting.db")
session_factory = async_sessionmaker(engine, expire_on_commit=False)
uow = AsyncSqlAlchemyUnitOfWork(session_factory)
clock = SystemClock()

get_parity = AsyncGetParityReport(uow=uow, clock=clock)

# Get parity report for all currencies
async with uow:
    report = await get_parity()

print(f"Parity Report ({report.generated_at}):")
print(f"  Base: {report.base_currency}")
print(f"  Total currencies: {report.total_currencies}")
print(f"  Has deviation: {report.has_deviation}")
for line in report.lines:
    base_marker = " [BASE]" if line.is_base else ""
    rate_str = f"rate={line.latest_rate}" if line.latest_rate else "rate=1.0"
    dev_str = f", dev={line.deviation_pct}%" if line.deviation_pct else ""
    print(f"    {line.currency_code}{base_marker}: {rate_str}{dev_str}")
```

**Filter Specific Currencies**:
```python
async with uow:
    report = await get_parity(codes=["USD", "EUR", "GBP"])
```

**See Also**:
- [ParityReportDTO](#parityreportdto) — Report data structure
- [ParityLineDTO](#paritylinedto) — Line data structure

---

#### AsyncGetTradingBalanceSnapshotReport

**Path**: `py_accountant.application.use_cases_async.reporting.AsyncGetTradingBalanceSnapshotReport`

**Purpose**: Produce trading balance snapshot in raw or detailed mode.

**Signature**:
```python
async def __call__(
    self,
    *,
    as_of: datetime | None = None,
    detailed: bool = False,
) -> TradingBalanceSnapshotDTO
```

**Parameters** (all keyword-only):
- `as_of` (datetime | None, optional) — Timestamp limiting inclusive end of window. Default: `clock.now()`.
- `detailed` (bool, optional) — If True, include converted base amounts (detailed mode); else raw mode. Default: False.

**Returns**: `TradingBalanceSnapshotDTO` — Snapshot with appropriate list populated and mode flag.

**Raises**:
- Same exceptions as underlying use cases:
  - `ValueError` — Invalid window
  - `ValidationError` — Domain validation issues (detailed mode requires base currency)

**Business Rules**:
1. Start of window defaults to epoch with same timezone as `clock.now()`
2. Raw mode: uses `AsyncGetTradingBalanceRaw`
3. Detailed mode: uses `AsyncGetTradingBalanceDetailed` (requires base currency)
4. One of `lines_raw` or `lines_detailed` is populated (other is None)
5. `mode` field indicates which list is populated

**Dependencies** (constructor injection):
- `uow: AsyncUnitOfWork` — Unit of Work for transaction management
- `clock: Clock` — Time provider for timestamps

**Example**:
```python
from datetime import datetime, UTC
from py_accountant.application.use_cases_async.reporting import AsyncGetTradingBalanceSnapshotReport
from py_accountant.infrastructure.persistence.sqlalchemy.uow import AsyncSqlAlchemyUnitOfWork
from py_accountant.infrastructure.persistence.inmemory.clock import SystemClock
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

# Setup
engine = create_async_engine("sqlite+aiosqlite:///accounting.db")
session_factory = async_sessionmaker(engine, expire_on_commit=False)
uow = AsyncSqlAlchemyUnitOfWork(session_factory)
clock = SystemClock()

get_snapshot = AsyncGetTradingBalanceSnapshotReport(uow=uow, clock=clock)

# Raw mode snapshot
async with uow:
    snapshot = await get_snapshot(detailed=False)

print(f"Trading Balance Snapshot ({snapshot.mode}):")
print(f"  As of: {snapshot.as_of}")
print(f"  Base currency: {snapshot.base_currency}")
if snapshot.lines_raw:
    for line in snapshot.lines_raw:
        print(f"    {line.currency_code}: net={line.net}")
```

**Detailed Mode**:
```python
async with uow:
    snapshot = await get_snapshot(detailed=True)

if snapshot.lines_detailed:
    for line in snapshot.lines_detailed:
        print(f"    {line.currency_code}: net={line.net} (base: {line.net_base})")
```

**See Also**:
- [AsyncGetTradingBalanceRaw](#asyncgettradingbalanceraw) — Raw balance
- [AsyncGetTradingBalanceDetailed](#asyncgettradingbalancedetailed) — Detailed balance
- [TradingBalanceSnapshotDTO](#tradingbalancesnapshotdto) — Snapshot data structure

---

## Protocols (Ports)

Protocols define interfaces that must be implemented by integrators to use the py_accountant use cases. They enable dependency injection and allow custom implementations (e.g., different databases, in-memory storage, external services).

### General Pattern

All protocols use Python's `typing.Protocol` for structural subtyping:

```python
from typing import Protocol

class SomeRepository(Protocol):
    """Repository protocol description."""
    
    async def some_method(self, param: Type) -> ResultType:
        """Method description."""
        ...
```

**Key Points**:
- Protocols are **structural** (duck-typed): no inheritance required
- Implement all methods with matching signatures
- Use `@runtime_checkable` decorator for isinstance() checks
- Reference implementations available in `py_accountant.infrastructure.persistence.sqlalchemy.*`

---

### Clock

**Path**: `py_accountant.application.ports.Clock`

**Purpose**: Abstraction for time provider to decouple current time from system clock (enables deterministic testing).

**Protocol Definition**:
```python
from datetime import datetime
from typing import Protocol

@runtime_checkable
class Clock(Protocol):
    """Clock abstraction to decouple time in tests.
    
    Implementations typically return timezone-aware UTC datetimes.
    """
    
    def now(self) -> datetime:
        """Get current time (timezone-aware).
        
        Returns:
            datetime with timezone info (typically UTC)
        """
        ...
```

**Methods**:
- `now() -> datetime` — Return current time as timezone-aware datetime.

**Reference Implementation**: `py_accountant.infrastructure.persistence.inmemory.clock.SystemClock`

**Requirements**:
1. Must return timezone-aware datetime (not naive)
2. Typically use UTC timezone
3. Should be deterministic in tests

**Example Implementation (Production)**:
```python
from datetime import datetime, UTC
from py_accountant.application.ports import Clock

class SystemClock:
    """Production clock using system time."""
    
    def now(self) -> datetime:
        return datetime.now(UTC)
```

**Example Implementation (Testing)**:
```python
from datetime import datetime, UTC
from py_accountant.application.ports import Clock

class FixedClock:
    """Fixed clock for deterministic testing."""
    
    def __init__(self, fixed_time: datetime):
        """Initialize with fixed time.
        
        Args:
            fixed_time: Timezone-aware datetime to always return
        """
        if fixed_time.tzinfo is None:
            raise ValueError("fixed_time must be timezone-aware")
        self.fixed_time = fixed_time
    
    def now(self) -> datetime:
        return self.fixed_time

# In test
clock = FixedClock(datetime(2025, 1, 15, 10, 30, tzinfo=UTC))
assert clock.now() == datetime(2025, 1, 15, 10, 30, tzinfo=UTC)
```

**Used In**:
- All use cases requiring timestamps (ledger, fx audit, reporting)
- Specifically: `AsyncPostTransaction`, `AsyncGetLedger`, `AsyncPlanFxAuditTTL`, `AsyncExecuteFxAuditTTL`, trading balance and reporting use cases

**See Also**:
- [SystemClock](../src/py_accountant/infrastructure/persistence/inmemory/clock.py) — Production implementation

---


