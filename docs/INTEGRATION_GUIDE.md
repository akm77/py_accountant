```bash
# 1) Миграции
poetry run alembic upgrade head
# 2) Базовые сущности
poetry run python -m presentation.cli.main currency add USD
poetry run python -m presentation.cli.main currency set-base USD
poetry run python -m presentation.cli.main account add Assets:Cash USD
# 3) Транзакция (две строки, суммы > 0)
poetry run python -m presentation.cli.main ledger post --line "DEBIT:Assets:Cash:50:USD" --line "CREDIT:Assets:Cash:50:USD" --json
# 4) Баланс счёта
poetry run python -m presentation.cli.main ledger balance Assets:Cash --json
# 5) Trading Detailed
poetry run python -m presentation.cli.main trading detailed --base USD --json
# 6) TTL план
poetry run python -m presentation.cli.main fx ttl-plan --retention-days 90 --batch-size 100 --mode delete --json
```

## 8. Форматы и сериализация

- Decimal → строки.
- datetime → ISO8601 с UTC (`Z`/aware); внутри домена — UTC.
- Квантизация: деньги — 2 знака, курсы — 6 знаков, округление ROUND_HALF_EVEN (см. `src/domain/quantize.py`).

## 9. FAQ / Траблшутинг (коротко)

| Проблема | Причина | Решение |
|----------|---------|---------|
| Alembic падает | async URL в `alembic.ini` | Храните async URL только в `DATABASE_URL_ASYNC` |
| SQLite locked | Параллельный доступ | Используйте Postgres или сериализуйте операции |
| Неверный баланс | Нарушен шаблон UoW | «Одна операция — один Async UoW», не шарьте сессии |
| Ошибка формата `--line` | Неверное количество полей | SIDE:Account:Amount:Currency[:Rate], суммы > 0 |

## 10. Пулы/таймауты/ретраи (async)

Для PostgreSQL (`postgresql+asyncpg`) доступны переменные окружения пула и таймаутов (детали в инфраструктуре). Для SQLite игнорируются.

---
Документ согласован с: `presentation/cli/*.py`, `application/use_cases_async/*`, `src/domain/quantize.py`, `docs/ARCHITECTURE_OVERVIEW.md`.
> Гайд по встраиванию py_accountant как библиотеки (SDK‑паттерн) в приложения: боты, веб‑сервисы, воркеры и периодические задачи.
>
> Ключевое: ядро async‑only. Интеграция выполняется через асинхронный слой. На каждый запрос/задачу — новый Async UoW.

## Runtime vs Migration Database URLs

Для безопасного использования async SQLAlchemy есть два URL:

| Назначение | Переменная | Пример | Допустимые драйверы |
|------------|-----------|--------|---------------------|
| Миграции (Alembic) | `DATABASE_URL` | `postgresql+psycopg://user:pass@host:5432/db` | `postgresql`, `postgresql+psycopg`, `sqlite`, `sqlite+pysqlite` |
| Runtime (async) | `DATABASE_URL_ASYNC` | `postgresql+asyncpg://user:pass@host:5432/db` | `postgresql+asyncpg`, `sqlite+aiosqlite` |

Правила:
- Alembic читает ТОЛЬКО `DATABASE_URL` (или fallback из `alembic.ini`).
- Если в `DATABASE_URL` указан async‑драйвер (`asyncpg`, `aiosqlite`) — миграции падают с RuntimeError.
- Приложение при отсутствии `DATABASE_URL_ASYNC` может нормализовать sync URL в async (см. инфраструктурный helper, если есть).
- CI: шаг миграций использует только sync URL.

Пример `.env`:
```
DATABASE_URL=postgresql+psycopg://acc:pass@localhost:5432/ledger
DATABASE_URL_ASYNC=postgresql+asyncpg://acc:pass@localhost:5432/ledger
LOG_LEVEL=INFO
```

Workflow:
```bash
poetry run alembic upgrade head   # использует DATABASE_URL (sync)
poetry run python -m presentation.cli.main trading detailed --base USD  # актуальная форма без двоеточий
```

WARNING: Не прописывайте async URL в `alembic.ini` — потеряется защита.

## 1. Быстрый старт (как библиотека, async‑only)

Минимальный рабочий пример на asyncio и async use cases. Один бизнес‑шаг — одна транзакция (один Async UoW).

```python
import asyncio
from datetime import datetime, UTC
from decimal import Decimal

from infrastructure.persistence.sqlalchemy.uow import AsyncSqlAlchemyUnitOfWork
from application.use_cases_async import (
    AsyncCreateCurrency,
    AsyncSetBaseCurrency,
    AsyncCreateAccount,
    AsyncPostTransaction,
    AsyncGetAccountBalance,
    AsyncGetTradingBalanceRaw,
    AsyncGetTradingBalanceDetailed,
)
from application.dto.models import EntryLineDTO

class SystemClock:
    """UTC‑часы для домена (junior‑friendly)."""
    def now(self) -> datetime:
        return datetime.now(UTC)

async def main() -> None:
    uow = AsyncSqlAlchemyUnitOfWork("sqlite+aiosqlite:///./example_async.db")

    # 1) Валюта и база
    async with uow:
        await AsyncCreateCurrency(uow)("USD")
        await AsyncSetBaseCurrency(uow)("USD")
        # commit произойдёт автоматически в __aexit__ при отсутствии ошибок

    # 2) Счёт
    async with uow:
        await AsyncCreateAccount(uow)("Assets:Cash", "USD")

    # 3) Транзакция
    async with uow:
        lines = [
            EntryLineDTO("DEBIT", "Assets:Cash", Decimal("100"), "USD"),
            EntryLineDTO("CREDIT", "Assets:Cash", Decimal("100"), "USD"),
        ]
        await AsyncPostTransaction(uow, SystemClock())(lines, memo="Init balance")

    # 4) Баланс
    async with uow:
        bal = await AsyncGetAccountBalance(uow, SystemClock())("Assets:Cash")
        print("Balance=", bal)

    # 5) Trading raw/detailed (опционально)
    async with uow:
        raw = await AsyncGetTradingBalanceRaw(uow, SystemClock())()
        det = await AsyncGetTradingBalanceDetailed(uow, SystemClock())(base_currency="USD")
        print("RAW count=", len(raw), "; DETAILED count=", len(det))

asyncio.run(main())
```

Принципы:
- «Одна операция — один Async UoW»: `async with uow: await use_case(...)`.
- При исключении — implicit rollback; иначе commit выполнится в `__aexit__`.
- Не хранить UoW/Session между запросами и корутинами.

## 2. CLI примеры (Typer‑группы, без двоеточий)

Точки входа: модуль `presentation.cli.main`. Проверить доступные команды: `diagnostics ping`, `currency`, `account`, `ledger`, `trading`, `fx`.

- Валюты:
  - Добавить валюту: `currency add USD`
  - Сделать базовой: `currency set-base USD`
  - Список: `currency list --json`
- Счета:
  - Создать: `account add Assets:Cash USD`
  - Получить: `account get Assets:Cash --json`
- Проводка и баланс:
  - Постинг: `ledger post --line "DEBIT:Assets:Cash:50:USD" --line "CREDIT:Assets:Cash:50:USD" --json`
  - Баланс: `ledger balance Assets:Cash --json`
- Trading:
  - Без конвертации: `trading raw --json`
  - С конвертацией: `trading detailed --base USD --json`
- FX Audit:
  - Добавить событие: `fx add-event USD 1.000000 --json`
  - Список событий: `fx list --json`
  - TTL план: `fx ttl-plan --retention-days 90 --batch-size 100 --mode delete --json`

Флаг `--line` принимает строки формата `SIDE:Account:Amount:Currency[:Rate]`.

## 3. Жизненный цикл и транзакции (async)

Шаблон:
```python
async with uow:
    await use_case(...)
    # при необходимости: await uow.commit() вручную; иначе commit произойдёт на выходе
```
- Исключение внутри блока → rollback и повторный выброс.
- Создавайте новый Async UoW на каждый запрос/задачу.

## 4. TTL (план в CLI, исполнение в SDK)

- В CLI есть ТОЛЬКО план: `fx ttl-plan ...` (источник: `src/presentation/cli/fx_audit.py`).
- Исполнение выполняйте в коде приложения через use cases.

```python
import asyncio
from datetime import datetime, UTC
from infrastructure.persistence.sqlalchemy.uow import AsyncSqlAlchemyUnitOfWork
from application.use_cases_async import AsyncPlanFxAuditTTL, AsyncExecuteFxAuditTTL

class SystemClock:
    def now(self):
        return datetime.now(UTC)

async def ttl_job():
    uow = AsyncSqlAlchemyUnitOfWork("postgresql+asyncpg://acc:pass@db:5432/ledger")
    async with uow:
        plan = await AsyncPlanFxAuditTTL(uow, SystemClock())(
            retention_days=90,
            batch_size=1000,
            mode="archive",  # none|delete|archive
            limit=None,
            dry_run=False,
        )
    # Выполнение плана — отдельной транзакцией
    async with uow:
        result = await AsyncExecuteFxAuditTTL(uow, SystemClock())(plan)
        print("TTL executed:", result.total_processed)

asyncio.run(ttl_job())
```

Параметры: `retention_days`, `batch_size`, `mode (none|delete|archive)`, `limit`, `dry_run`. Даты — ISO8601 UTC, Decimal сериализуются строкой (см. «Форматы» ниже).

## 5. Telegram Bot (асинхронный)

Пример в `examples/telegram_bot/*`. Принципы:
- На каждый хендлер — новый `AsyncSqlAlchemyUnitOfWork` (фабрика).
- Используемые async use cases: `AsyncListCurrencies`, `AsyncListExchangeRateEvents`, `AsyncGetAccountBalance`, `AsyncPostTransaction`.
- Строка транзакции для `/tx`: `SIDE:Account:Amount:Currency[:Rate]` (две строки обязаны балансировать).

Псевдокод регистрации:
```python
from examples.telegram_bot.handlers import register_handlers, router
from infrastructure.persistence.sqlalchemy.uow import AsyncSqlAlchemyUnitOfWork

def uow_factory():
    return AsyncSqlAlchemyUnitOfWork("sqlite+aiosqlite:///./bot.db")

register_handlers(uow_factory, settings=None)
```

## 6. Настройка окружения

`.env`:
```
DATABASE_URL=postgresql+psycopg://user:pass@host:5432/dbname  # для Alembic
DATABASE_URL_ASYNC=postgresql+asyncpg://user:pass@host:5432/dbname  # для рантайма
LOG_LEVEL=INFO
JSON_LOGS=false
```
Миграции:
```bash
poetry run alembic upgrade head
```
Логирование (кратко):
```python
from infrastructure.logging.config import configure_logging
configure_logging()
```

## 7. Smoke сценарии

- Если ретраи исчерпаны — выбрасывается исходное исключение.
