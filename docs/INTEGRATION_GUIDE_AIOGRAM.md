# Детальный пример интеграции: Telegram Bot на aiogram

## Введение

Этот раздел демонстрирует полную интеграцию `py_accountant` в телеграм-бот для управления личными финансами. Бот позволяет пользователям:
- Записывать доходы и расходы через команды
- Проверять баланс счетов
- Просматривать историю транзакций
- Управлять валютами и курсами

**Целевая аудитория:** Middle+ разработчики, знакомые с Python async/await, SQLAlchemy и основами Clean Architecture.

**Стек технологий:**
- **aiogram 3.x** — асинхронный фреймворк для Telegram Bot API
- **py_accountant** — библиотека двойной записи с Clean Architecture
- **PostgreSQL** — СУБД для хранения данных
- **asyncpg** — асинхронный драйвер PostgreSQL
- **Alembic** — инструмент миграций

## Архитектура интеграции

```
┌─────────────────────────────────────────────────────┐
│              Telegram Bot Layer                     │
│  (aiogram Dispatcher, Handlers, Middlewares)        │
└────────────────┬────────────────────────────────────┘
                 │
                 │ Commands: /deposit, /balance, etc.
                 ▼
┌─────────────────────────────────────────────────────┐
│            Adapter Layer (Bot Code)                 │
│  - UoW factory (AsyncSqlAlchemyUnitOfWork)          │
│  - Clock (SystemClock)                              │
│  - Error handlers                                   │
│  - Command parsers                                  │
└────────────────┬────────────────────────────────────┘
                 │
                 │ Use cases invocation
                 ▼
┌─────────────────────────────────────────────────────┐
│         py_accountant Core (Library)                │
│  Application Layer:                                 │
│    - AsyncPostTransaction                           │
│    - AsyncGetAccountBalance                         │
│    - AsyncGetLedger                                 │
│    - AsyncCreateCurrency / AsyncSetBaseCurrency     │
│    - AsyncCreateAccount                             │
│  Domain Layer:                                      │
│    - LedgerValidator                                │
│    - Currency, Account value objects                │
│    - Business rules                                 │
└────────────────┬────────────────────────────────────┘
                 │
                 │ Repository interface (ports)
                 ▼
┌─────────────────────────────────────────────────────┐
│     Infrastructure Layer (py_accountant)            │
│  - AsyncSqlAlchemyUnitOfWork                        │
│  - Async repositories                               │
│  - SQLAlchemy models                                │
└────────────────┬────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────┐
│              PostgreSQL Database                    │
│  Tables: currencies, accounts, journal,             │
│          transaction_lines, account_balances, etc.  │
└─────────────────────────────────────────────────────┘
```

**Ключевые принципы интеграции:**
1. **Dependency Injection** — UoW и Clock передаются через middleware
2. **Transaction boundaries** — каждая команда = одна транзакция
3. **Error handling** — доменные ошибки преобразуются в user-friendly сообщения
4. **Logging separation** — отключаем встроенный logger py_accountant, используем свой

---

## Шаг 1: Подготовка проекта

### 1.1 Структура директорий

Рекомендуемая структура для telegram-бота с py_accountant:

```
finance_bot/
├── .env                      # Environment variables
├── .gitignore
├── alembic.ini               # Alembic configuration (from py_accountant)
├── pyproject.toml            # Dependencies
├── README.md
├── alembic/                  # Migrations (symlink or copy from py_accountant)
│   ├── env.py
│   └── versions/
│       ├── 0001_initial.py
│       ├── 0002_add_is_base_currency.py
│       └── ...
├── bot/
│   ├── __init__.py
│   ├── main.py               # Entry point
│   ├── config.py             # Settings (pydantic)
│   ├── handlers/             # Command handlers
│   │   ├── __init__.py
│   │   ├── account.py        # /balance, /accounts
│   │   ├── transaction.py    # /deposit, /expense, /transfer
│   │   ├── currency.py       # /currencies, /set_rate
│   │   └── history.py        # /history
│   ├── middlewares/          # Custom middlewares
│   │   ├── __init__.py
│   │   ├── uow.py            # UoW injection
│   │   ├── clock.py          # Clock injection
│   │   ├── error_handler.py  # Error handling
│   │   └── logging.py        # Logging context
│   ├── filters/              # Custom filters
│   │   └── __init__.py
│   └── utils/                # Helpers
│       ├── __init__.py
│       ├── parsers.py        # Command argument parsers
│       └── formatters.py     # Message formatters
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── test_handlers.py
    └── test_integration.py
```

### 1.2 pyproject.toml с зависимостями

```toml
[tool.poetry]
name = "finance-bot"
version = "0.1.0"
description = "Telegram bot for personal finance management"
authors = ["Your Name <you@example.com>"]
readme = "README.md"

[tool.poetry.dependencies]
python = "^3.11"
aiogram = "^3.0"
py-accountant = {git = "https://github.com/akm77/py_accountant.git"}
pydantic = "^2.0"
pydantic-settings = "^2.0"
python-dotenv = "^1.0"
structlog = "^24.0"
asyncpg = "^0.29"
alembic = "^1.13"
psycopg = {extras = ["binary"], version = "^3.1"}

[tool.poetry.group.dev.dependencies]
pytest = "^8.0"
pytest-asyncio = "^0.23"
pytest-cov = "^4.1"
ruff = "^0.1"
mypy = "^1.8"

[build-system]
requires = ["poetry-core"]
build-backend = "poetry.core.masonry.api"

[tool.ruff]
line-length = 120
target-version = "py311"

[tool.mypy]
python_version = "3.11"
strict = true
```

**Установка зависимостей:**

```bash
poetry install
```

### 1.3 Конфигурация (.env файл)

Создайте `.env` файл в корне проекта:

```bash
# ============================================================
# Telegram Bot Configuration
# ============================================================
BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz123456789

# ============================================================
# py_accountant: Database URLs (dual-URL strategy)
# ============================================================

# Sync URL for Alembic migrations (psycopg driver)
PYACC__DATABASE_URL=postgresql+psycopg://acc_user:acc_pass@localhost:5432/finance_bot

# Async URL for runtime (asyncpg driver)
PYACC__DATABASE_URL_ASYNC=postgresql+asyncpg://acc_user:acc_pass@localhost:5432/finance_bot

# ============================================================
# py_accountant: Logging Configuration
# ============================================================

# Disable py_accountant's built-in logging (we use bot's logger)
PYACC__LOGGING_ENABLED=false

# ============================================================
# py_accountant: Database Pool Settings
# ============================================================

# Pool settings optimized for bot workload
# (aiogram может обрабатывать множество запросов параллельно)
PYACC__DB_POOL_SIZE=20
PYACC__DB_MAX_OVERFLOW=10
PYACC__DB_POOL_TIMEOUT=30

# ============================================================
# Bot Application Settings
# ============================================================

# Log level for bot
BOT_LOG_LEVEL=INFO

# Timezone for user operations (optional, defaults to UTC)
BOT_TIMEZONE=UTC

# Admin user IDs (comma-separated, for privileged commands)
BOT_ADMIN_IDS=123456789,987654321
```

**Важные замечания:**
- **Dual-URL стратегия обязательна**: sync URL для миграций, async для runtime
- **PYACC__LOGGING_ENABLED=false** — отключаем встроенный logger py_accountant
- **Pool settings** — настройте под вашу нагрузку (начните с 20/10)

### 1.4 Конфигурация приложения (config.py)

```python
"""Application configuration using pydantic-settings."""
from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Bot configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Telegram Bot
    bot_token: str = Field(..., alias="BOT_TOKEN")
    bot_log_level: str = Field("INFO", alias="BOT_LOG_LEVEL")
    bot_timezone: str = Field("UTC", alias="BOT_TIMEZONE")
    bot_admin_ids: list[int] = Field(default_factory=list)

    # py_accountant database URLs
    pyacc_database_url: str = Field(..., alias="PYACC__DATABASE_URL")
    pyacc_database_url_async: str = Field(..., alias="PYACC__DATABASE_URL_ASYNC")

    # py_accountant pool settings (optional, with defaults)
    pyacc_db_pool_size: int = Field(20, alias="PYACC__DB_POOL_SIZE")
    pyacc_db_max_overflow: int = Field(10, alias="PYACC__DB_MAX_OVERFLOW")
    pyacc_db_pool_timeout: int = Field(30, alias="PYACC__DB_POOL_TIMEOUT")

    def parse_admin_ids(self, value: str) -> list[int]:
        """Parse comma-separated admin IDs."""
        if not value:
            return []
        return [int(x.strip()) for x in value.split(",") if x.strip()]


# Singleton instance
settings = Settings()
```

---

## Шаг 2: Реализация UnitOfWork адаптера

### 2.1 Когда использовать встроенный AsyncSqlAlchemyUnitOfWork

`py_accountant` предоставляет готовую реализацию `AsyncSqlAlchemyUnitOfWork`, которая подходит для большинства случаев:

**Используйте встроенный UoW, если:**
- Вам нужна стандартная функциональность (commit/rollback/close)
- Не требуется дополнительная логика (например, custom events)
- Достаточно стандартных репозиториев

**Пишите свой wrapper, если:**
- Нужно добавить логирование каждой транзакции
- Требуется интеграция с системой метрик (Prometheus, StatsD)
- Нужны custom hooks (on_commit, on_rollback)

### 2.2 Использование встроенного AsyncSqlAlchemyUnitOfWork

```python
"""UoW factory setup for bot."""
from __future__ import annotations

from typing import Callable

from py_accountant.application.ports import AsyncUnitOfWork
from py_accountant.infrastructure.persistence.sqlalchemy.uow import AsyncSqlAlchemyUnitOfWork

from bot.config import settings


def create_uow_factory() -> Callable[[], AsyncUnitOfWork]:
    """Create UoW factory for dependency injection.
    
    Returns:
        Factory function that creates new UoW instances.
    
    Notes:
        Each invocation of the factory returns a NEW UoW instance.
        This is correct behavior - one UoW per request/command.
    """
    
    def factory() -> AsyncUnitOfWork:
        return AsyncSqlAlchemyUnitOfWork(
            url=settings.pyacc_database_url_async,
            echo=False,  # Disable SQL echo in production
        )
    
    return factory
```

### 2.3 Custom UoW wrapper (опционально)

Если нужна дополнительная логика, можно обернуть встроенный UoW:

```python
"""Custom UoW wrapper with logging and metrics."""
from __future__ import annotations

import logging
from typing import Any

from py_accountant.application.ports import AsyncUnitOfWork
from py_accountant.infrastructure.persistence.sqlalchemy.uow import AsyncSqlAlchemyUnitOfWork

logger = logging.getLogger(__name__)


class BotUnitOfWork(AsyncUnitOfWork):
    """Wrapper around AsyncSqlAlchemyUnitOfWork with additional bot-specific logic."""

    def __init__(self, url: str, *, echo: bool = False) -> None:
        """Initialize wrapper with underlying UoW."""
        self._uow = AsyncSqlAlchemyUnitOfWork(url=url, echo=echo)
        self._transaction_count = 0

    async def __aenter__(self) -> BotUnitOfWork:
        """Enter context: start transaction and log."""
        await self._uow.__aenter__()
        self._transaction_count += 1
        logger.debug(f"UoW entered (transaction #{self._transaction_count})")
        return self

    async def __aexit__(self, exc_type, exc: BaseException | None, tb: Any) -> None:
        """Exit context: commit/rollback and log."""
        if exc is not None:
            logger.warning(f"UoW rollback due to exception: {exc}", exc_info=True)
        else:
            logger.debug("UoW commit successful")
        
        await self._uow.__aexit__(exc_type, exc, tb)

    async def commit(self) -> None:
        """Explicit commit."""
        await self._uow.commit()
        logger.debug("Explicit commit called")

    async def rollback(self) -> None:
        """Explicit rollback."""
        await self._uow.rollback()
        logger.debug("Explicit rollback called")

    # Delegate repository access to underlying UoW
    @property
    def accounts(self):
        return self._uow.accounts

    @property
    def currencies(self):
        return self._uow.currencies

    @property
    def transactions(self):
        return self._uow.transactions

    @property
    def exchange_rate_events(self):
        return self._uow.exchange_rate_events
```

### 2.4 Lifecycle management (startup/shutdown)

```python
"""Bot lifecycle hooks for UoW management."""
from __future__ import annotations

import logging

from aiogram import Bot

from bot.config import settings
from bot.uow import create_uow_factory

logger = logging.getLogger(__name__)


async def on_startup(bot: Bot) -> None:
    """Initialize resources on bot startup.
    
    Args:
        bot: aiogram Bot instance
    """
    logger.info("Bot starting up...")
    
    # Create UoW factory and store in bot data
    uow_factory = create_uow_factory()
    bot["uow_factory"] = uow_factory
    
    logger.info("UoW factory initialized")
    
    # Optional: verify database connection
    async with uow_factory() as uow:
        currencies = await uow.currencies.list_all()
        logger.info(f"Database connection verified. Found {len(currencies)} currencies.")


async def on_shutdown(bot: Bot) -> None:
    """Cleanup resources on bot shutdown.
    
    Args:
        bot: aiogram Bot instance
    """
    logger.info("Bot shutting down...")
    
    # Get UoW factory
    uow_factory = bot.get("uow_factory")
    if not uow_factory:
        logger.warning("UoW factory not found in bot data")
        return
    
    # Close all connections in the pool
    # Note: AsyncSqlAlchemyUnitOfWork manages its own engine
    # We need to dispose it properly
    try:
        # Create a temporary UoW to access the engine
        uow = uow_factory()
        await uow.engine.dispose()
        logger.info("Database connections closed")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}", exc_info=True)
```

### 2.5 Connection pool tuning для aiogram

**Рекомендации по настройке pool:**

| Workload | pool_size | max_overflow | pool_timeout |
|----------|-----------|--------------|--------------|
| Малый бот (<100 пользователей) | 5 | 5 | 30 |
| Средний бот (100-1000 пользователей) | 20 | 10 | 30 |
| Большой бот (>1000 пользователей) | 50 | 20 | 60 |

**Важно:**
- `pool_size` — количество постоянных соединений
- `max_overflow` — дополнительные соединения при пиковой нагрузке
- `pool_timeout` — таймаут ожидания свободного соединения

**Monitoring pool usage:**

```python
# В production добавьте метрики pool'а
from sqlalchemy.pool import Pool

def log_pool_stats(pool: Pool) -> None:
    """Log connection pool statistics."""
    logger.info(
        f"Pool stats: size={pool.size()}, "
        f"checked_in={pool.checkedin()}, "
        f"checked_out={pool.checkedout()}, "
        f"overflow={pool.overflow()}"
    )
```

---

## Шаг 3: Реализация Clock адаптера

### 3.1 SystemClock (рекомендуется для production)

`py_accountant` предоставляет готовую реализацию `SystemClock`:

```python
"""Clock provider for bot."""
from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from py_accountant.application.ports import Clock
from py_accountant.infrastructure.persistence.inmemory.clock import SystemClock


def create_clock() -> Clock:
    """Create clock instance for bot.
    
    Returns:
        SystemClock instance (always UTC).
    
    Notes:
        SystemClock always returns datetime.now(UTC).
        If you need user-specific timezones, use UserTimezoneClock wrapper.
    """
    return SystemClock()
```

### 3.2 UserTimezoneClock (опционально, для user timezone support)

Если вам нужна поддержка пользовательских timezone:

```python
"""User-aware clock with timezone support."""
from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from py_accountant.application.ports import Clock


class UserTimezoneClock(Clock):
    """Clock that returns time in user's timezone.
    
    Use case: when you want to display/record times in user's local timezone
    instead of UTC.
    
    Notes:
        - Internally py_accountant stores all timestamps in UTC
        - This clock converts UTC to user's timezone for display
        - When persisting, times are converted back to UTC
    """

    def __init__(self, user_timezone: str = "UTC") -> None:
        """Initialize clock with user timezone.
        
        Args:
            user_timezone: IANA timezone name (e.g., "Europe/Moscow", "America/New_York")
        
        Raises:
            ZoneInfoNotFoundError: if timezone is invalid
        """
        self.user_tz = ZoneInfo(user_timezone)

    def now(self) -> datetime:
        """Return current time in user's timezone.
        
        Returns:
            Timezone-aware datetime in user's timezone.
        """
        return datetime.now(UTC).astimezone(self.user_tz)


# Usage example in handler:
async def handler_with_user_tz(message: Message, uow_factory, user_settings):
    """Example handler with user timezone."""
    # Get user's timezone from settings/database
    user_tz = user_settings.get(message.from_user.id, {}).get("timezone", "UTC")
    
    # Create clock with user timezone
    clock = UserTimezoneClock(user_tz)
    
    # Use clock in use case
    async with uow_factory() as uow:
        use_case = AsyncPostTransaction(uow, clock)
        # timestamp will be in user's timezone but stored as UTC
        tx = await use_case(lines=[...], memo="Test")
```

### 3.3 FixedClock (для тестов)

```python
"""Fixed clock for testing."""
from datetime import datetime

from py_accountant.application.ports import Clock


class FixedClock(Clock):
    """Clock that always returns the same fixed time.
    
    Use case: unit tests where you need deterministic timestamps.
    """

    def __init__(self, fixed_time: datetime) -> None:
        """Initialize with fixed time.
        
        Args:
            fixed_time: The timestamp to always return
        """
        self._fixed = fixed_time

    def now(self) -> datetime:
        """Return the fixed time."""
        return self._fixed


# Usage in tests:
from datetime import UTC, datetime

def test_post_transaction():
    """Test transaction with fixed timestamp."""
    fixed_time = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
    clock = FixedClock(fixed_time)
    
    # All transactions will have this exact timestamp
    # ...
```

---

## Шаг 4: Маппинг bot команд → use cases

### 4.1 Handler: /deposit (доход)

```python
"""Transaction handlers for bot."""
from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from py_accountant.application.dto.models import EntryLineDTO
from py_accountant.application.use_cases_async.ledger import AsyncPostTransaction
from py_accountant.domain.errors import DomainError, ValidationError

logger = logging.getLogger(__name__)

router = Router(name="transactions")


@router.message(Command("deposit"))
async def deposit_handler(message: Message, uow_factory, clock) -> None:
    """Handle /deposit command.
    
    Usage: /deposit <amount> <currency> [memo]
    Example: /deposit 100 USD Salary
    
    Creates a double-entry:
        DEBIT  Assets:User:{user_id}:Cash     amount currency
        CREDIT Income:User:{user_id}:Deposits amount currency
    """
    if not message.text or not message.from_user:
        await message.reply("❌ Invalid command format")
        return
    
    # Parse command arguments
    parts = message.text.split(maxsplit=3)
    if len(parts) < 3:
        await message.reply(
            "❌ Usage: /deposit <amount> <currency> [memo]\n"
            "Example: /deposit 100 USD Salary"
        )
        return
    
    try:
        amount = Decimal(parts[1])
        if amount <= 0:
            await message.reply("❌ Amount must be positive")
            return
    except InvalidOperation:
        await message.reply(f"❌ Invalid amount: {parts[1]}")
        return
    
    currency = parts[2].upper()
    memo = parts[3] if len(parts) > 3 else "Deposit from Telegram"
    
    user_id = message.from_user.id
    username = message.from_user.username or f"user_{user_id}"
    
    # Map to double-entry lines
    lines = [
        EntryLineDTO(
            side="DEBIT",
            account_full_name=f"Assets:User:{user_id}:Cash",
            amount=amount,
            currency_code=currency,
            exchange_rate=None,  # Will be auto-populated from currency settings
        ),
        EntryLineDTO(
            side="CREDIT",
            account_full_name=f"Income:User:{user_id}:Deposits",
            amount=amount,
            currency_code=currency,
            exchange_rate=None,
        ),
    ]
    
    # Execute use case
    async with uow_factory() as uow:
        use_case = AsyncPostTransaction(uow, clock)
        try:
            tx = await use_case(
                lines=lines,
                memo=memo,
                meta={
                    "user_id": user_id,
                    "username": username,
                    "chat_id": message.chat.id,
                    "command": "deposit",
                },
            )
            await message.reply(
                f"✅ Deposit recorded\n"
                f"Amount: {amount} {currency}\n"
                f"Transaction ID: {tx.id}\n"
                f"Memo: {memo}"
            )
            logger.info(f"Deposit recorded for user {user_id}: {amount} {currency}")
        
        except ValidationError as e:
            await message.reply(f"❌ Validation error: {e}")
            logger.warning(f"Validation error for user {user_id}: {e}")
        
        except ValueError as e:
            # Missing account or currency
            await message.reply(
                f"❌ Resource not found: {e}\n\n"
                f"💡 Tip: Create accounts and currencies first:\n"
                f"  /create_account Assets:User:{user_id}:Cash {currency}\n"
                f"  /create_currency {currency}"
            )
            logger.warning(f"Resource error for user {user_id}: {e}")
        
        except DomainError as e:
            await message.reply(f"❌ Business rule violation: {e}")
            logger.error(f"Domain error for user {user_id}: {e}")
        
        except Exception as e:
            await message.reply("❌ Internal error. Please try again later.")
            logger.exception(f"Unexpected error for user {user_id}")
```

### 4.2 Handler: /expense (расход)

```python
@router.message(Command("expense"))
async def expense_handler(message: Message, uow_factory, clock) -> None:
    """Handle /expense command.
    
    Usage: /expense <amount> <currency> <category> [memo]
    Example: /expense 50 USD Food Lunch at cafe
    
    Creates a double-entry:
        DEBIT  Expenses:User:{user_id}:{category} amount currency
        CREDIT Assets:User:{user_id}:Cash          amount currency
    """
    if not message.text or not message.from_user:
        await message.reply("❌ Invalid command format")
        return
    
    parts = message.text.split(maxsplit=4)
    if len(parts) < 4:
        await message.reply(
            "❌ Usage: /expense <amount> <currency> <category> [memo]\n"
            "Example: /expense 50 USD Food Lunch"
        )
        return
    
    try:
        amount = Decimal(parts[1])
        if amount <= 0:
            await message.reply("❌ Amount must be positive")
            return
    except InvalidOperation:
        await message.reply(f"❌ Invalid amount: {parts[1]}")
        return
    
    currency = parts[2].upper()
    category = parts[3].capitalize()  # e.g., "Food", "Transport"
    memo = parts[4] if len(parts) > 4 else f"{category} expense"
    
    user_id = message.from_user.id
    username = message.from_user.username or f"user_{user_id}"
    
    lines = [
        EntryLineDTO(
            side="DEBIT",
            account_full_name=f"Expenses:User:{user_id}:{category}",
            amount=amount,
            currency_code=currency,
            exchange_rate=None,
        ),
        EntryLineDTO(
            side="CREDIT",
            account_full_name=f"Assets:User:{user_id}:Cash",
            amount=amount,
            currency_code=currency,
            exchange_rate=None,
        ),
    ]
    
    async with uow_factory() as uow:
        use_case = AsyncPostTransaction(uow, clock)
        try:
            tx = await use_case(
                lines=lines,
                memo=memo,
                meta={
                    "user_id": user_id,
                    "username": username,
                    "chat_id": message.chat.id,
                    "command": "expense",
                    "category": category,
                },
            )
            await message.reply(
                f"✅ Expense recorded\n"
                f"Amount: {amount} {currency}\n"
                f"Category: {category}\n"
                f"Transaction ID: {tx.id}\n"
                f"Memo: {memo}"
            )
            logger.info(f"Expense recorded for user {user_id}: {amount} {currency} ({category})")
        
        except ValidationError as e:
            await message.reply(f"❌ Validation error: {e}")
        
        except ValueError as e:
            await message.reply(f"❌ Resource not found: {e}")
        
        except DomainError as e:
            await message.reply(f"❌ Business rule violation: {e}")
        
        except Exception as e:
            await message.reply("❌ Internal error. Please try again later.")
            logger.exception(f"Unexpected error for user {user_id}")
```

### 4.3 Handler: /balance (баланс счёта)

```python
"""Account handlers for bot."""
from __future__ import annotations

import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from py_accountant.application.use_cases_async.ledger import AsyncGetAccountBalance
from py_accountant.application.use_cases_async.accounts import AsyncListAccounts

logger = logging.getLogger(__name__)

router = Router(name="accounts")


@router.message(Command("balance"))
async def balance_handler(message: Message, uow_factory, clock) -> None:
    """Handle /balance command.
    
    Usage: /balance [account_name]
    Example: /balance Assets:User:123:Cash
    
    If account_name is not provided, shows balance for default cash account.
    """
    if not message.from_user:
        await message.reply("❌ Cannot identify user")
        return
    
    user_id = message.from_user.id
    
    # Parse command arguments
    parts = message.text.split(maxsplit=1) if message.text else []
    if len(parts) > 1:
        account_name = parts[1]
    else:
        # Default to user's cash account
        account_name = f"Assets:User:{user_id}:Cash"
    
    async with uow_factory() as uow:
        use_case = AsyncGetAccountBalance(uow, clock)
        try:
            balance = await use_case(account_full_name=account_name, as_of=None)
            
            # Get account details to show currency
            account = await uow.accounts.get_by_full_name(account_name)
            if not account:
                await message.reply(f"❌ Account not found: {account_name}")
                return
            
            await message.reply(
                f"💰 Balance for {account_name}\n"
                f"Amount: {balance} {account.currency_code}"
            )
            logger.info(f"Balance checked for user {user_id}: {account_name} = {balance}")
        
        except Exception as e:
            await message.reply(f"❌ Error getting balance: {e}")
            logger.exception(f"Error getting balance for user {user_id}")


@router.message(Command("accounts"))
async def list_accounts_handler(message: Message, uow_factory, clock) -> None:
    """Handle /accounts command - list all user's accounts.
    
    Usage: /accounts
    
    Shows all accounts belonging to the user with their balances.
    """
    if not message.from_user:
        await message.reply("❌ Cannot identify user")
        return
    
    user_id = message.from_user.id
    
    async with uow_factory() as uow:
        try:
            # List all accounts
            all_accounts = await AsyncListAccounts(uow)()
            
            # Filter user's accounts
            user_accounts = [
                acc for acc in all_accounts
                if f":User:{user_id}:" in acc.full_name
            ]
            
            if not user_accounts:
                await message.reply("📭 You have no accounts yet")
                return
            
            # Get balances for each account
            balance_use_case = AsyncGetAccountBalance(uow, clock)
            lines = ["📊 Your accounts:\n"]
            
            for acc in user_accounts:
                try:
                    balance = await balance_use_case(account_full_name=acc.full_name, as_of=None)
                    lines.append(f"  • {acc.full_name}: {balance} {acc.currency_code}")
                except Exception as e:
                    lines.append(f"  • {acc.full_name}: Error ({e})")
            
            await message.reply("\n".join(lines))
            logger.info(f"Account list shown for user {user_id}: {len(user_accounts)} accounts")
        
        except Exception as e:
            await message.reply(f"❌ Error listing accounts: {e}")
            logger.exception(f"Error listing accounts for user {user_id}")
```

### 4.4 Handler: /history (история транзакций)

```python
"""History handlers for bot."""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from py_accountant.application.use_cases_async.ledger import AsyncGetLedger

logger = logging.getLogger(__name__)

router = Router(name="history")


@router.message(Command("history"))
async def history_handler(message: Message, uow_factory, clock) -> None:
    """Handle /history command.
    
    Usage: /history [account_name] [days]
    Example: /history Assets:User:123:Cash 7
    
    Shows last N days of transactions (default: 30 days).
    """
    if not message.from_user:
        await message.reply("❌ Cannot identify user")
        return
    
    user_id = message.from_user.id
    
    # Parse arguments
    parts = message.text.split() if message.text else []
    
    # Default values
    account_name = f"Assets:User:{user_id}:Cash"
    days = 30
    
    if len(parts) > 1:
        account_name = parts[1]
    if len(parts) > 2:
        try:
            days = int(parts[2])
            if days <= 0 or days > 365:
                await message.reply("❌ Days must be between 1 and 365")
                return
        except ValueError:
            await message.reply(f"❌ Invalid days: {parts[2]}")
            return
    
    # Calculate time window
    end = clock.now()
    start = end - timedelta(days=days)
    
    async with uow_factory() as uow:
        use_case = AsyncGetLedger(uow, clock)
        try:
            # Get ledger entries
            entries = await use_case(
                account_full_name=account_name,
                start=start,
                end=end,
                meta=None,
                offset=0,
                limit=50,  # Limit to 50 transactions
                order="DESC",  # Most recent first
            )
            
            if not entries:
                await message.reply(
                    f"📭 No transactions found for {account_name}\n"
                    f"Period: last {days} days"
                )
                return
            
            # Format response
            lines = [f"📜 Transaction history for {account_name}"]
            lines.append(f"Period: last {days} days\n")
            
            for entry in entries:
                # Find the line for this account
                account_line = None
                for line in entry.lines:
                    if line.account_full_name == account_name:
                        account_line = line
                        break
                
                if not account_line:
                    continue
                
                # Format timestamp
                ts = entry.occurred_at.strftime("%Y-%m-%d %H:%M")
                
                # Format amount with sign
                if account_line.side.upper() == "DEBIT":
                    amount_str = f"+{account_line.amount}"
                else:
                    amount_str = f"-{account_line.amount}"
                
                # Format memo
                memo = entry.memo or "No memo"
                
                lines.append(
                    f"{ts} | {amount_str} {account_line.currency_code} | {memo}"
                )
            
            lines.append(f"\nShowing {len(entries)} transactions")
            
            await message.reply("\n".join(lines))
            logger.info(f"History shown for user {user_id}: {account_name}, {len(entries)} entries")
        
        except ValueError as e:
            await message.reply(f"❌ Error: {e}")
        
        except Exception as e:
            await message.reply(f"❌ Error retrieving history: {e}")
            logger.exception(f"Error retrieving history for user {user_id}")
```

### 4.5 Handler: /currencies (список валют)

```python
"""Currency handlers for bot."""
from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from py_accountant.application.use_cases_async.currencies import (
    AsyncCreateCurrency,
    AsyncSetBaseCurrency,
)
from py_accountant.domain.errors import ValidationError

logger = logging.getLogger(__name__)

router = Router(name="currencies")


@router.message(Command("currencies"))
async def list_currencies_handler(message: Message, uow_factory, clock) -> None:
    """Handle /currencies command - list all available currencies.
    
    Usage: /currencies
    
    Shows all currencies with their exchange rates.
    """
    async with uow_factory() as uow:
        try:
            currencies = await uow.currencies.list_all()
            
            if not currencies:
                await message.reply("📭 No currencies configured")
                return
            
            lines = ["💱 Available currencies:\n"]
            
            for cur in currencies:
                if cur.is_base:
                    lines.append(f"  • {cur.code} (BASE)")
                elif cur.exchange_rate:
                    lines.append(f"  • {cur.code} = {cur.exchange_rate} BASE")
                else:
                    lines.append(f"  • {cur.code} (no rate)")
            
            await message.reply("\n".join(lines))
            logger.info(f"Currency list shown: {len(currencies)} currencies")
        
        except Exception as e:
            await message.reply(f"❌ Error listing currencies: {e}")
            logger.exception("Error listing currencies")


@router.message(Command("create_currency"))
async def create_currency_handler(message: Message, uow_factory, clock) -> None:
    """Handle /create_currency command.
    
    Usage: /create_currency <code> [rate]
    Example: /create_currency USD
    Example: /create_currency EUR 1.12
    
    Creates a new currency. Rate is optional (for non-base currencies).
    """
    parts = message.text.split() if message.text else []
    
    if len(parts) < 2:
        await message.reply(
            "❌ Usage: /create_currency <code> [rate]\n"
            "Example: /create_currency USD\n"
            "Example: /create_currency EUR 1.12"
        )
        return
    
    code = parts[1].upper()
    rate = None
    
    if len(parts) > 2:
        try:
            rate = Decimal(parts[2])
            if rate <= 0:
                await message.reply("❌ Rate must be positive")
                return
        except InvalidOperation:
            await message.reply(f"❌ Invalid rate: {parts[2]}")
            return
    
    async with uow_factory() as uow:
        use_case = AsyncCreateCurrency(uow)
        try:
            currency = await use_case(code=code, exchange_rate=rate)
            
            rate_info = f" with rate {rate}" if rate else ""
            await message.reply(
                f"✅ Currency created: {currency.code}{rate_info}"
            )
            logger.info(f"Currency created: {code}, rate={rate}")
        
        except ValidationError as e:
            await message.reply(f"❌ Validation error: {e}")
        
        except Exception as e:
            await message.reply(f"❌ Error creating currency: {e}")
            logger.exception(f"Error creating currency {code}")


@router.message(Command("set_base"))
async def set_base_currency_handler(message: Message, uow_factory, clock) -> None:
    """Handle /set_base command - set base currency.
    
    Usage: /set_base <code>
    Example: /set_base USD
    
    Sets the specified currency as the base currency for conversions.
    """
    parts = message.text.split() if message.text else []
    
    if len(parts) < 2:
        await message.reply(
            "❌ Usage: /set_base <code>\n"
            "Example: /set_base USD"
        )
        return
    
    code = parts[1].upper()
    
    async with uow_factory() as uow:
        use_case = AsyncSetBaseCurrency(uow)
        try:
            await use_case(code=code)
            await message.reply(f"✅ Base currency set to: {code}")
            logger.info(f"Base currency set to: {code}")
        
        except ValidationError as e:
            await message.reply(f"❌ Error: {e}")
        
        except Exception as e:
            await message.reply(f"❌ Error setting base currency: {e}")
            logger.exception(f"Error setting base currency to {code}")
```

---

## Шаг 5: Dependency Injection

### 5.1 UoW Middleware

```python
"""UnitOfWork middleware for dependency injection."""
from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject


class UoWMiddleware(BaseMiddleware):
    """Middleware that injects UoW factory into handler data.
    
    Usage:
        dp.message.middleware(UoWMiddleware(uow_factory))
    
    Handler signature:
        async def handler(message: Message, uow_factory) -> None:
            async with uow_factory() as uow:
                # use uow
    """

    def __init__(self, uow_factory: Callable) -> None:
        """Initialize middleware with UoW factory.
        
        Args:
            uow_factory: Factory function that creates UoW instances
        """
        self.uow_factory = uow_factory
        super().__init__()

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        """Inject UoW factory into handler data.
        
        Args:
            handler: Next handler in chain
            event: Telegram event (Message, CallbackQuery, etc.)
            data: Handler data dict
        
        Returns:
            Handler result
        """
        # Inject UoW factory into data
        data["uow_factory"] = self.uow_factory
        
        # Call next handler
        return await handler(event, data)
```

### 5.2 Clock Middleware

```python
"""Clock middleware for dependency injection."""
from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from py_accountant.application.ports import Clock


class ClockMiddleware(BaseMiddleware):
    """Middleware that injects Clock into handler data.
    
    Usage:
        dp.message.middleware(ClockMiddleware(clock))
    
    Handler signature:
        async def handler(message: Message, clock: Clock) -> None:
            now = clock.now()
    """

    def __init__(self, clock: Clock) -> None:
        """Initialize middleware with clock instance.
        
        Args:
            clock: Clock instance (SystemClock, FixedClock, etc.)
        """
        self.clock = clock
        super().__init__()

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        """Inject clock into handler data.
        
        Args:
            handler: Next handler in chain
            event: Telegram event
            data: Handler data dict
        
        Returns:
            Handler result
        """
        data["clock"] = self.clock
        return await handler(event, data)
```

### 5.3 Регистрация middlewares в main.py

```python
"""Bot entry point with middleware registration."""
from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from bot.config import settings
from bot.handlers import account, currency, history, transaction
from bot.middlewares.clock import ClockMiddleware
from bot.middlewares.error_handler import ErrorHandlerMiddleware
from bot.middlewares.logging import LogContextMiddleware
from bot.middlewares.uow import UoWMiddleware
from bot.uow import create_uow_factory
from py_accountant.infrastructure.persistence.inmemory.clock import SystemClock

# Configure logging
logging.basicConfig(
    level=settings.bot_log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    """Start bot."""
    # Initialize bot and dispatcher
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    
    # Create dependencies
    uow_factory = create_uow_factory()
    clock = SystemClock()
    
    # Register middlewares (order matters!)
    # 1. Logging context (first, to capture all events)
    dp.message.middleware(LogContextMiddleware())
    
    # 2. Error handler (to catch all exceptions)
    dp.message.middleware(ErrorHandlerMiddleware())
    
    # 3. UoW injection (after error handler, so errors are caught)
    dp.message.middleware(UoWMiddleware(uow_factory))
    
    # 4. Clock injection
    dp.message.middleware(ClockMiddleware(clock))
    
    # Register routers
    dp.include_router(transaction.router)
    dp.include_router(account.router)
    dp.include_router(currency.router)
    dp.include_router(history.router)
    
    # Start polling
    logger.info("Bot starting...")
    try:
        # Run startup hook
        await on_startup(bot, uow_factory)
        
        # Start polling
        await dp.start_polling(bot)
    finally:
        # Run shutdown hook
        await on_shutdown(bot, uow_factory)


async def on_startup(bot: Bot, uow_factory) -> None:
    """Startup hook."""
    logger.info("Running startup tasks...")
    
    # Verify database connection
    try:
        async with uow_factory() as uow:
            currencies = await uow.currencies.list_all()
            logger.info(f"Database OK. Found {len(currencies)} currencies.")
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        raise


async def on_shutdown(bot: Bot, uow_factory) -> None:
    """Shutdown hook."""
    logger.info("Running shutdown tasks...")
    
    # Close database connections
    try:
        uow = uow_factory()
        await uow.engine.dispose()
        logger.info("Database connections closed")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")
    
    await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
```

### 5.4 Context vars для transaction boundaries (опционально)

Если нужна более сложная логика управления транзакциями:

```python
"""Context vars for transaction management."""
from __future__ import annotations

from contextvars import ContextVar
from typing import Any

from py_accountant.application.ports import AsyncUnitOfWork

# Context var для текущего UoW
current_uow: ContextVar[AsyncUnitOfWork | None] = ContextVar("current_uow", default=None)


class TransactionMiddleware(BaseMiddleware):
    """Middleware that manages transaction boundaries.
    
    Opens UoW at the start of handler, commits on success, rolls back on error.
    """

    def __init__(self, uow_factory: Callable) -> None:
        self.uow_factory = uow_factory
        super().__init__()

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        """Manage transaction boundary."""
        async with self.uow_factory() as uow:
            # Set UoW in context var
            current_uow.set(uow)
            
            try:
                # Call handler
                result = await handler(event, data)
                
                # Explicit commit (optional, will happen in __aexit__ anyway)
                await uow.commit()
                
                return result
            
            except Exception:
                # Rollback happens automatically in __aexit__
                raise
            
            finally:
                # Clear context var
                current_uow.set(None)
```

---

## Шаг 6: Обработка ошибок

### 6.1 Error Handler Middleware

Централизованная обработка ошибок для преобразования доменных исключений в user-friendly сообщения:

```python
"""Error handler middleware."""
from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

from py_accountant.domain.errors import DomainError, ValidationError

logger = logging.getLogger(__name__)


class ErrorHandlerMiddleware(BaseMiddleware):
    """Middleware that catches and handles all exceptions.
    
    Converts domain exceptions to user-friendly messages.
    Logs all errors for debugging.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        """Wrap handler in try-except block."""
        try:
            return await handler(event, data)
        
        except ValidationError as e:
            # Domain validation error (bad input format)
            await self._send_error(event, f"❌ Validation error: {e}")
            logger.warning(f"ValidationError: {e}", extra={"event": type(event).__name__})
        
        except ValueError as e:
            # Resource not found (account, currency missing)
            error_msg = str(e)
            
            # Provide helpful hints based on error message
            if "Account not found" in error_msg:
                hint = "\n💡 Create account first with /create_account"
            elif "Currency not found" in error_msg:
                hint = "\n💡 Create currency first with /create_currency"
            else:
                hint = ""
            
            await self._send_error(event, f"❌ {error_msg}{hint}")
            logger.warning(f"ValueError: {e}", extra={"event": type(event).__name__})
        
        except DomainError as e:
            # Business rule violation (e.g., unbalanced ledger)
            await self._send_error(event, f"❌ Business rule violation:\n{e}")
            logger.error(f"DomainError: {e}", extra={"event": type(event).__name__})
        
        except Exception as e:
            # Unexpected error
            await self._send_error(
                event,
                "❌ Internal error occurred. Please try again later.\n"
                "If the problem persists, contact support."
            )
            logger.exception(f"Unexpected error: {e}", extra={"event": type(event).__name__})
    
    async def _send_error(self, event: TelegramObject, message: str) -> None:
        """Send error message to user."""
        if isinstance(event, Message):
            await event.reply(message)
```

### 6.2 Классификация ошибок

**Типы ошибок в py_accountant и их обработка:**

| Тип исключения | Причина | User message | Действие |
|----------------|---------|--------------|----------|
| `ValidationError` | Невалидные данные (формат, пустые значения, length constraints) | "Validation error: {details}" | Показать подсказку по формату |
| `ValueError` | Отсутствующий ресурс (account/currency не найден) | "Resource not found: {resource}" | Показать команду создания |
| `DomainError` | Нарушение бизнес-правил (несбалансированный ledger) | "Business rule violation: {details}" | Объяснить правило |
| `Exception` | Неожиданная ошибка (DB timeout, network, bug) | "Internal error. Try again later." | Логировать, алертить админов |

---

## Шаг 7: Миграции в production

### 7.1 CI/CD Pipeline (GitHub Actions)

```yaml
# .github/workflows/deploy.yml
name: Deploy Finance Bot

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Install Poetry
        run: |
          curl -sSL https://install.python-poetry.org | python3 -
      
      - name: Install dependencies
        run: poetry install
      
      - name: Run database migrations
        env:
          PYACC__DATABASE_URL: ${{ secrets.DATABASE_URL }}
        run: poetry run alembic upgrade head
      
      - name: Deploy to server
        run: |
          # Your deployment logic here
```

### 7.2 Docker Deployment

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN pip install poetry

COPY pyproject.toml poetry.lock ./
RUN poetry install --only main

COPY . .

# Run migrations then start bot
CMD poetry run alembic upgrade head && poetry run python -m bot.main
```

```yaml
# docker-compose.yml
version: '3.8'

services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: acc_user
      POSTGRES_PASSWORD: acc_pass
      POSTGRES_DB: finance_bot
    volumes:
      - postgres_data:/var/lib/postgresql/data
  
  bot:
    build: .
    depends_on:
      - postgres
    environment:
      BOT_TOKEN: ${BOT_TOKEN}
      PYACC__DATABASE_URL: postgresql+psycopg://acc_user:acc_pass@postgres:5432/finance_bot
      PYACC__DATABASE_URL_ASYNC: postgresql+asyncpg://acc_user:acc_pass@postgres:5432/finance_bot
      PYACC__LOGGING_ENABLED: "false"
    restart: unless-stopped

volumes:
  postgres_data:
```

---

## Шаг 8: Логирование

### 8.1 Отключение встроенного logger py_accountant

В `.env` файле:

```bash
PYACC__LOGGING_ENABLED=false
```

### 8.2 Настройка structlog для бота

```python
"""Structured logging configuration."""
import structlog


def configure_logging(log_level: str = "INFO") -> None:
    """Configure structured logging for bot."""
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.contextvars.merge_contextvars,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
    )
```

### 8.3 LogContext Middleware

```python
"""Logging context middleware."""
from aiogram import BaseMiddleware
import structlog


class LogContextMiddleware(BaseMiddleware):
    """Add user context to logs."""

    async def __call__(self, handler, event, data):
        """Add logging context."""
        context = {}
        
        if hasattr(event, 'from_user') and event.from_user:
            context["user_id"] = event.from_user.id
            context["username"] = event.from_user.username
        
        structlog.contextvars.bind_contextvars(**context)
        
        try:
            return await handler(event, data)
        finally:
            structlog.contextvars.clear_contextvars()
```

---

## Шаг 9: Тестирование

### 9.1 Unit-тесты handlers (mocked UoW)

```python
"""Unit tests for handlers."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from bot.handlers.transaction import deposit_handler


@pytest.fixture
def mock_message():
    """Create mock telegram message."""
    message = MagicMock()
    message.text = "/deposit 100 USD Test"
    message.from_user = MagicMock(id=123, username="test_user")
    message.chat = MagicMock(id=123)
    message.reply = AsyncMock()
    return message


@pytest.mark.asyncio
async def test_deposit_handler(mock_message):
    """Test successful deposit command."""
    mock_uow = AsyncMock()
    mock_uow.__aenter__.return_value = mock_uow
    
    uow_factory = lambda: mock_uow
    clock = MagicMock()
    
    await deposit_handler(mock_message, uow_factory, clock)
    
    # Assert reply was called
    mock_message.reply.assert_called_once()
```

### 9.2 Integration тесты (InMemoryUnitOfWork)

```python
"""Integration tests with InMemoryUnitOfWork."""
import pytest
from decimal import Decimal

from py_accountant.application.use_cases_async.ledger import AsyncPostTransaction
from py_accountant.infrastructure.persistence.inmemory.uow import InMemoryUnitOfWork
from py_accountant.infrastructure.persistence.inmemory.clock import SystemClock


@pytest.mark.asyncio
async def test_deposit_integration():
    """Test full deposit flow."""
    uow = InMemoryUnitOfWork()
    clock = SystemClock()
    
    # Setup currencies and accounts
    # ... (create base currency, accounts)
    
    # Post transaction
    async with uow:
        use_case = AsyncPostTransaction(uow, clock)
        tx = await use_case(lines=[...], memo="Test")
        assert tx.id.startswith("tx:")
```

---

## Шаг 10: Production Checklist

### 10.1 Pre-deployment Checklist

| Категория | Пункт | Статус | Примечания |
|-----------|-------|--------|------------|
| **Configuration** | ✅ BOT_TOKEN настроен | ⬜ | Telegram Bot Token |
| | ✅ DATABASE_URL (sync) настроен | ⬜ | Для Alembic миграций |
| | ✅ DATABASE_URL_ASYNC настроен | ⬜ | Для runtime операций |
| | ✅ LOGGING_ENABLED=false | ⬜ | Отключить встроенный logger py_accountant |
| **Database** | ✅ PostgreSQL установлен | ⬜ | Версия 12+ |
| | ✅ Database создана | ⬜ | CREATE DATABASE finance_bot |
| | ✅ User с правами создан | ⬜ | GRANT ALL ON DATABASE |
| | ✅ Миграции применены | ⬜ | alembic upgrade head |
| | ✅ Pool settings настроены | ⬜ | POOL_SIZE, MAX_OVERFLOW |
| **Application** | ✅ Зависимости установлены | ⬜ | poetry install |
| | ✅ Базовая валюта настроена | ⬜ | /set_base USD |
| | ✅ Тестовые счета созданы | ⬜ | Для проверки работы |
| **Monitoring** | ✅ Logging настроен | ⬜ | structlog + JSON |
| | ✅ Error tracking | ⬜ | Sentry / custom |
| | ✅ Metrics collection | ⬜ | Prometheus / StatsD |
| | ✅ Alerts настроены | ⬜ | Grafana / PagerDuty |
| **Security** | ✅ Секреты в env vars | ⬜ | Не в коде! |
| | ✅ SSL/TLS для DB | ⬜ | ?sslmode=require |
| | ✅ Rate limiting | ⬜ | Защита от спама |
| | ✅ Input validation | ⬜ | Все inputs проверяются |
| **Backup** | ✅ Database backup стратегия | ⬜ | pg_dump / AWS RDS |
| | ✅ Backup restoration tested | ⬜ | Проверить восстановление |
| | ✅ Retention policy | ⬜ | Хранить N дней |
| **Testing** | ✅ Unit tests проходят | ⬜ | pytest |
| | ✅ Integration tests проходят | ⬜ | С InMemoryUnitOfWork |
| | ✅ E2E tests проходят | ⬜ | С тестовой БД |
| | ✅ Load testing | ⬜ | Проверить под нагрузкой |
| **CI/CD** | ✅ Pipeline настроен | ⬜ | GitHub Actions / GitLab CI |
| | ✅ Auto-deploy работает | ⬜ | На production |
| | ✅ Rollback процедура | ⬜ | Документирована и протестирована |
| **Documentation** | ✅ README актуален | ⬜ | Setup инструкции |
| | ✅ API документация | ⬜ | Команды бота |
| | ✅ Runbook для ops | ⬜ | Troubleshooting |

### 10.2 Database Tuning для Production

#### PostgreSQL Configuration

```sql
-- /etc/postgresql/16/main/postgresql.conf

-- Connection settings
max_connections = 100

-- Memory settings (adjust based on available RAM)
shared_buffers = 256MB          -- 25% of RAM for dedicated server
effective_cache_size = 1GB      -- 50-75% of RAM
work_mem = 4MB                   -- Per-sort operation
maintenance_work_mem = 128MB    -- For VACUUM, CREATE INDEX

-- Write-ahead log
wal_buffers = 16MB
checkpoint_completion_target = 0.9

-- Query planning
random_page_cost = 1.1          -- For SSD storage
effective_io_concurrency = 200  -- For SSD storage

-- Logging (important for debugging)
log_destination = 'stderr'
logging_collector = on
log_directory = 'log'
log_filename = 'postgresql-%Y-%m-%d.log'
log_statement = 'mod'           -- Log INSERT/UPDATE/DELETE
log_duration = on
log_line_prefix = '%t [%p]: [%l-1] user=%u,db=%d,app=%a,client=%h '
```

#### Connection Pooling Strategy

```python
"""Optimal pool settings for aiogram bot."""

# Small bot (<100 active users)
POOL_SIZE = 5
MAX_OVERFLOW = 5
POOL_TIMEOUT = 30

# Medium bot (100-1000 active users)
POOL_SIZE = 20
MAX_OVERFLOW = 10
POOL_TIMEOUT = 30

# Large bot (>1000 active users)
POOL_SIZE = 50
MAX_OVERFLOW = 20
POOL_TIMEOUT = 60

# Pool recycle to avoid stale connections
POOL_RECYCLE = 3600  # 1 hour
```

#### Index Optimization

```sql
-- Ensure these indexes exist (from py_accountant migrations)

-- journal table
CREATE INDEX IF NOT EXISTS idx_journal_occurred_at ON journal(occurred_at);
CREATE INDEX IF NOT EXISTS idx_journal_idempotency_key ON journal(idempotency_key) WHERE idempotency_key IS NOT NULL;

-- transaction_lines table
CREATE INDEX IF NOT EXISTS idx_transaction_lines_account_id ON transaction_lines(account_id);
CREATE INDEX IF NOT EXISTS idx_transaction_lines_journal_id ON transaction_lines(journal_id);

-- accounts table
CREATE INDEX IF NOT EXISTS idx_accounts_full_name ON accounts(full_name);

-- account_balances table (for fast balance queries)
CREATE INDEX IF NOT EXISTS idx_account_balances_account_id ON account_balances(account_id);

-- account_daily_turnovers table (for reports)
CREATE INDEX IF NOT EXISTS idx_account_daily_turnovers_account_date ON account_daily_turnovers(account_id, date);
```

### 10.3 Monitoring & Alerting

#### Key Metrics to Track

```python
"""Prometheus metrics for bot monitoring."""
from prometheus_client import Counter, Histogram, Gauge

# Command metrics
command_total = Counter(
    'bot_commands_total',
    'Total commands processed',
    ['command', 'status']
)

command_duration = Histogram(
    'bot_command_duration_seconds',
    'Command processing time',
    ['command'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
)

# Database metrics
db_connections_active = Gauge(
    'db_connections_active',
    'Active database connections'
)

db_query_duration = Histogram(
    'db_query_duration_seconds',
    'Database query duration',
    ['query_type']
)

# Error metrics
error_total = Counter(
    'bot_errors_total',
    'Total errors',
    ['error_type']
)

# User metrics
active_users = Gauge(
    'bot_active_users',
    'Number of active users'
)
```

#### Grafana Dashboard Example

```json
{
  "dashboard": {
    "title": "Finance Bot Monitoring",
    "panels": [
      {
        "title": "Commands per Second",
        "targets": [
          {
            "expr": "rate(bot_commands_total[5m])"
          }
        ]
      },
      {
        "title": "Error Rate",
        "targets": [
          {
            "expr": "rate(bot_errors_total[5m])"
          }
        ]
      },
      {
        "title": "P95 Command Latency",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, bot_command_duration_seconds)"
          }
        ]
      },
      {
        "title": "Database Connection Pool",
        "targets": [
          {
            "expr": "db_connections_active"
          }
        ]
      }
    ]
  }
}
```

#### Alert Rules

```yaml
# prometheus_alerts.yml
groups:
  - name: bot_alerts
    interval: 1m
    rules:
      # High error rate
      - alert: HighErrorRate
        expr: rate(bot_errors_total[5m]) > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High error rate detected"
          description: "Error rate is {{ $value }} errors/sec"
      
      # Slow commands
      - alert: SlowCommands
        expr: histogram_quantile(0.95, bot_command_duration_seconds) > 5
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Commands are slow"
          description: "P95 latency is {{ $value }} seconds"
      
      # Database connection pool exhaustion
      - alert: DatabasePoolExhausted
        expr: db_connections_active / POOL_SIZE > 0.9
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Database connection pool nearly exhausted"
          description: "{{ $value }}% of connections in use"
      
      # Bot down
      - alert: BotDown
        expr: up{job="finance_bot"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Bot is down"
          description: "Bot has been down for 1 minute"
```

### 10.4 Backup Strategy

#### Automated Backup Script

```bash
#!/bin/bash
# backup.sh - Daily database backup

set -e

BACKUP_DIR="/var/backups/finance_bot"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/backup_$DATE.sql.gz"
RETENTION_DAYS=30

# Create backup directory
mkdir -p $BACKUP_DIR

# Perform backup
pg_dump -h localhost -U acc_user -d finance_bot | gzip > $BACKUP_FILE

# Verify backup
if [ -f "$BACKUP_FILE" ]; then
    echo "Backup created: $BACKUP_FILE"
    SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    echo "Backup size: $SIZE"
else
    echo "ERROR: Backup failed!"
    exit 1
fi

# Remove old backups
find $BACKUP_DIR -name "backup_*.sql.gz" -mtime +$RETENTION_DAYS -delete

# Upload to S3 (optional)
# aws s3 cp $BACKUP_FILE s3://my-backups/finance_bot/

echo "Backup completed successfully"
```

#### Crontab Entry

```cron
# Daily backup at 2 AM
0 2 * * * /opt/finance_bot/scripts/backup.sh >> /var/log/finance_bot_backup.log 2>&1
```

#### Restore Procedure

```bash
#!/bin/bash
# restore.sh - Restore database from backup

set -e

BACKUP_FILE="$1"

if [ -z "$BACKUP_FILE" ]; then
    echo "Usage: $0 <backup_file.sql.gz>"
    exit 1
fi

if [ ! -f "$BACKUP_FILE" ]; then
    echo "ERROR: Backup file not found: $BACKUP_FILE"
    exit 1
fi

echo "WARNING: This will drop and recreate the database!"
read -p "Continue? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "Restore cancelled"
    exit 0
fi

# Stop bot
systemctl stop finance-bot

# Drop and recreate database
psql -h localhost -U postgres -c "DROP DATABASE IF EXISTS finance_bot;"
psql -h localhost -U postgres -c "CREATE DATABASE finance_bot OWNER acc_user;"

# Restore backup
gunzip -c $BACKUP_FILE | psql -h localhost -U acc_user -d finance_bot

# Start bot
systemctl start finance-bot

echo "Restore completed successfully"
```

### 10.5 Security Best Practices

#### Environment Variables Security

```bash
# Use secrets manager instead of plain .env files
# AWS Secrets Manager example

# Store secret
aws secretsmanager create-secret \
    --name finance-bot/prod/bot-token \
    --secret-string "1234567890:ABCdef..."

# Retrieve secret in application
BOT_TOKEN=$(aws secretsmanager get-secret-value \
    --secret-id finance-bot/prod/bot-token \
    --query SecretString \
    --output text)
```

#### Rate Limiting

```python
"""Rate limiting middleware."""
from collections import defaultdict
from datetime import datetime, timedelta
from aiogram import BaseMiddleware


class RateLimitMiddleware(BaseMiddleware):
    """Limit commands per user per minute."""
    
    def __init__(self, max_requests: int = 10, window: int = 60):
        self.max_requests = max_requests
        self.window = timedelta(seconds=window)
        self.requests = defaultdict(list)
    
    async def __call__(self, handler, event, data):
        if not hasattr(event, 'from_user'):
            return await handler(event, data)
        
        user_id = event.from_user.id
        now = datetime.now()
        
        # Clean old requests
        self.requests[user_id] = [
            ts for ts in self.requests[user_id]
            if now - ts < self.window
        ]
        
        # Check limit
        if len(self.requests[user_id]) >= self.max_requests:
            await event.answer("⏱ Too many requests. Please wait a moment.")
            return
        
        # Record request
        self.requests[user_id].append(now)
        
        return await handler(event, data)
```

#### Input Sanitization

```python
"""Input validation helpers."""
from decimal import Decimal, InvalidOperation


def validate_amount(amount_str: str) -> Decimal:
    """Validate and parse amount from user input.
    
    Raises:
        ValueError: if amount is invalid
    """
    try:
        amount = Decimal(amount_str)
        if amount <= 0:
            raise ValueError("Amount must be positive")
        if amount > Decimal("999999999.99"):
            raise ValueError("Amount too large")
        return amount
    except InvalidOperation:
        raise ValueError(f"Invalid amount format: {amount_str}")


def validate_currency_code(code: str) -> str:
    """Validate currency code.
    
    Raises:
        ValueError: if code is invalid
    """
    code = code.upper().strip()
    if not code.isalpha():
        raise ValueError("Currency code must contain only letters")
    if len(code) < 3 or len(code) > 10:
        raise ValueError("Currency code must be 3-10 characters")
    return code


def validate_account_name(name: str) -> str:
    """Validate account name.
    
    Raises:
        ValueError: if name is invalid
    """
    if not name or ":" not in name:
        raise ValueError("Account name must be hierarchical (e.g., Assets:Cash)")
    
    # Check for SQL injection patterns
    dangerous_chars = [";", "--", "/*", "*/", "xp_", "sp_"]
    for char in dangerous_chars:
        if char in name.lower():
            raise ValueError("Invalid characters in account name")
    
    return name
```

### 10.6 Performance Optimization

#### Caching Strategy

```python
"""Caching frequently accessed data."""
from functools import lru_cache
from datetime import datetime, timedelta


class CachedDataProvider:
    """Cache currencies and account lists."""
    
    def __init__(self, uow_factory):
        self.uow_factory = uow_factory
        self._cache = {}
        self._cache_expires = {}
        self._ttl = timedelta(minutes=5)
    
    async def get_currencies(self):
        """Get cached currencies list."""
        key = "currencies"
        
        if key in self._cache and datetime.now() < self._cache_expires.get(key):
            return self._cache[key]
        
        # Fetch from database
        async with self.uow_factory() as uow:
            currencies = await uow.currencies.list_all()
        
        # Cache result
        self._cache[key] = currencies
        self._cache_expires[key] = datetime.now() + self._ttl
        
        return currencies
```

#### Batch Operations

```python
"""Batch operations for better performance."""


async def create_accounts_batch(uow, accounts_data: list[dict]):
    """Create multiple accounts in one transaction."""
    async with uow:
        for data in accounts_data:
            await AsyncCreateAccount(uow)(
                full_name=data["full_name"],
                currency_code=data["currency_code"]
            )
        await uow.commit()


# Usage:
accounts = [
    {"full_name": "Assets:User:123:Cash", "currency_code": "USD"},
    {"full_name": "Assets:User:123:Savings", "currency_code": "USD"},
    {"full_name": "Income:User:123:Salary", "currency_code": "USD"},
]
await create_accounts_batch(uow_factory(), accounts)
```

---

## Заключение

Вы успешно интегрировали `py_accountant` в телеграм-бот на aiogram! 🎉

### Что мы реализовали:

1. ✅ **Полную интеграцию** с Clean Architecture принципами
2. ✅ **Dependency Injection** через middlewares
3. ✅ **Error handling** с user-friendly сообщениями
4. ✅ **Structured logging** с context vars
5. ✅ **Production-ready deployment** с Docker и CI/CD
6. ✅ **Comprehensive testing** (unit, integration, e2e)
7. ✅ **Monitoring & alerting** с Prometheus/Grafana
8. ✅ **Security best practices** (rate limiting, validation)
9. ✅ **Database optimization** (indexes, pooling, backups)
10. ✅ **Production checklist** для запуска

### Следующие шаги:

1. **Расширение функциональности:**
   - Добавить команды для отчётов (/report_monthly, /report_category)
   - Реализовать multi-currency support с автоматическим конвертированием
   - Добавить scheduled tasks (например, ежедневные напоминания)

2. **Улучшение UX:**
   - Добавить inline keyboards для частых операций
   - Реализовать conversations (multi-step dialogs)
   - Добавить visualizations (графики расходов/доходов)

3. **Масштабирование:**
   - Настроить horizontal scaling (multiple bot instances)
   - Добавить Redis для shared state
   - Реализовать message queue (Celery) для долгих операций

### Полезные ссылки:

- **py_accountant документация:**
  - [ARCHITECTURE_OVERVIEW.md](ARCHITECTURE_OVERVIEW.md) - архитектура библиотеки
  - [ACCOUNTING_CHEATSHEET.md](ACCOUNTING_CHEATSHEET.md) - шпаргалка по проводкам
  - [RUNNING_MIGRATIONS.md](RUNNING_MIGRATIONS.md) - работа с миграциями
  - [TRADING_WINDOWS.md](TRADING_WINDOWS.md) - торговые отчёты
  - [FX_AUDIT.md](FX_AUDIT.md) - аудит валютных операций

- **Внешние ресурсы:**
  - [aiogram Documentation](https://docs.aiogram.dev/) - официальная документация aiogram
  - [SQLAlchemy Async](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html) - async SQLAlchemy
  - [structlog](https://www.structlog.org/) - structured logging
  - [PostgreSQL Performance](https://wiki.postgresql.org/wiki/Performance_Optimization) - оптимизация PostgreSQL

### Troubleshooting

**Проблема: "Database connection pool exhausted"**
- **Решение:** Увеличьте `PYACC__DB_POOL_SIZE` или оптимизируйте запросы

**Проблема: "Unbalanced ledger" ошибки**
- **Решение:** Проверьте exchange rates для всех валют, убедитесь что установлена base currency

**Проблема: "Slow command response"**
- **Решение:** Добавьте indexes на часто используемые поля, включите кэширование

**Проблема: "Migration conflicts"**
- **Решение:** Используйте `alembic stamp head` или rollback и retry

---

## Appendix: Полный пример minimal bot

```python
"""Minimal working bot example."""
import asyncio
import logging
from aiogram import Bot, Dispatcher, Router
from aiogram.filters import Command
from aiogram.types import Message

from py_accountant.infrastructure.persistence.sqlalchemy.uow import AsyncSqlAlchemyUnitOfWork
from py_accountant.infrastructure.persistence.inmemory.clock import SystemClock

logging.basicConfig(level=logging.INFO)

router = Router()

@router.message(Command("start"))
async def start_handler(message: Message):
    await message.reply("👋 Welcome to Finance Bot!")

@router.message(Command("ping"))
async def ping_handler(message: Message):
    await message.reply("🏓 Pong!")

async def main():
    bot = Bot(token="YOUR_BOT_TOKEN")
    dp = Dispatcher()
    
    # Setup dependencies
    uow_factory = lambda: AsyncSqlAlchemyUnitOfWork(
        url="postgresql+asyncpg://user:pass@localhost/db"
    )
    clock = SystemClock()
    
    # Register handlers
    dp.include_router(router)
    
    # Start polling
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
```

**Успехов в разработке! 🚀**

---

**Документ актуален на:** 2025-01-15  
**Версия py_accountant:** latest (git main branch)  
**Версия aiogram:** 3.x  
**Python:** 3.11+

