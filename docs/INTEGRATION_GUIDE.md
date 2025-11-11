# INTEGRATION_GUIDE

> Гайд по встраиванию py-accountant как библиотеки (SDK-паттерн) в приложения: боты, веб-сервисы, воркеры и периодические задачи.
>
> Цель: обеспечить простое использование ��дра без изменения публичного API и без новых зависимостей в основном пакете.

## Runtime vs Migration Database URLs

Для безопасного перехода на async SQLAlchemy введено два URL:

| Назначение | Переменная | Пример | Допустимые драйверы |
|------------|-----------|--------|---------------------|
| Миграции (Alembic) | `DATABASE_URL` | `postgresql+psycopg://user:pass@host:5432/db` | `postgresql`, `postgresql+psycopg`, `sqlite`, `sqlite+pysqlite` |
| Runtime (async) | `DATABASE_URL_ASYNC` | `postgresql+asyncpg://user:pass@host:5432/db` | `postgresql+asyncpg`, `sqlite+aiosqlite` |

Правила:
- Alembic читает ТОЛЬКО `DATABASE_URL` (или fallback из `alembic.ini`).
- Если в `DATABASE_URL` указан async драйвер (`asyncpg`, `aiosqlite`) — миграции падают с RuntimeError.
- Приложение при отсутствии `DATABASE_URL_ASYNC` может нормализовать sync URL в async (см. `normalize_async_url`).
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
poetry run python -m presentation.cli.main trading:detailed --base USD
```

WARNING: Не прописывать async URL в `alembic.ini` — потеряется защита.

## 1. Быстрый старт (как библиотека)

Минимальный цикл работы через `SqlAlchemyUnitOfWork`.

```python
from infrastructure.persistence.sqlalchemy.uow import SqlAlchemyUnitOfWork
from application.use_cases.ledger import CreateCurrency, CreateAccount, PostTransaction, GetBalance, GetTradingBalance
from application.dto.models import EntryLineDTO
from datetime import timezone, datetime
from dataclasses import dataclass
from decimal import Decimal

@dataclass
class SystemClock:
    tz = timezone.utc
    def now(self) -> datetime:
        return datetime.now(self.tz)

clock = SystemClock()

db_url = "sqlite+pysqlite:///./example.db"
uow = SqlAlchemyUnitOfWork(db_url)

# 1. Создать базовую валюту
CreateCurrency(uow)("USD")
uow.currencies.set_base("USD")
# 2. Создать счёт
CreateAccount(uow)("Assets:Cash", "USD")
# 3. Провести транзакцию
lines = [
    EntryLineDTO(side="DEBIT", account_full_name="Assets:Cash", amount=Decimal("100"), currency_code="USD"),
    EntryLineDTO(side="CREDIT", account_full_name="Assets:Cash", amount=Decimal("0"), currency_code="USD"),
]
PostTransaction(uow, clock)(lines, memo="Init balance")
# 4. Коммит
uow.commit()
# 5. Баланс
balance = GetBalance(uow, clock)("Assets:Cash")
print("Balance=", balance)
# 6. Trading balance (агрегат по валютам)
trading = GetTradingBalance(uow, clock)(base_currency="USD")
print(trading.base_total)
```

Use cases (основные):
- `CreateCurrency(code, exchange_rate?)`
- `CreateAccount(full_name, currency_code)`
- `PostTransaction(lines, memo?, meta?)`
- `GetBalance(account_full_name, as_of?, recompute?)`
- `GetTradingBalance(base_currency?, start?, end?, as_of?)`
- `ListLedger` / `GetLedger` для доступа к журналу
- `UpdateExchangeRates(updates, set_base?)`
- `RecalculateAccountBalance(account_full_name, as_of?)`

Ошибки бизнес-логики порождают `DomainError`.

### Рецепты

Создать валюту с курсом (не базовая):
```python
from infrastructure.persistence.sqlalchemy.uow import SqlAlchemyUnitOfWork
from application.use_cases.ledger import CreateCurrency
from decimal import Decimal

uow = SqlAlchemyUnitOfWork("sqlite+pysqlite:///:memory:")
CreateCurrency(uow)("EUR", exchange_rate=Decimal("1.1234"))
```

Провести многострочную транзакцию:
```python
from infrastructure.persistence.sqlalchemy.uow import SqlAlchemyUnitOfWork
from application.use_cases.ledger import CreateCurrency, CreateAccount, PostTransaction
from application.dto.models import EntryLineDTO
from datetime import timezone, datetime
from dataclasses import dataclass
from decimal import Decimal

@dataclass
class SystemClock:
    tz = timezone.utc
    def now(self) -> datetime:
        return datetime.now(self.tz)

clock = SystemClock()
uow = SqlAlchemyUnitOfWork("sqlite+pysqlite:///:memory:")
CreateCurrency(uow)("USD", exchange_rate=Decimal("1"))
CreateAccount(uow)("Assets:Cash", "USD")
CreateAccount(uow)("Income:Sales", "USD")
lines = [
    EntryLineDTO("DEBIT", "Assets:Cash", amount=Decimal("150"), currency_code="USD"),
    EntryLineDTO("CREDIT", "Income:Sales", amount=Decimal("150"), currency_code="USD"),
]
PostTransaction(uow, clock)(lines, memo="Sale #42")
uow.commit()
```

Получить подробный trading balance c конвертаци��й:
```python
from infrastructure.persistence.sqlalchemy.uow import SqlAlchemyUnitOfWork
from application.use_cases.ledger import CreateCurrency, CreateAccount, GetTradingBalanceDetailed
from datetime import timezone, datetime
from dataclasses import dataclass
from decimal import Decimal

@dataclass
class SystemClock:
    tz = timezone.utc
    def now(self) -> datetime:
        return datetime.now(self.tz)

clock = SystemClock()
uow = SqlAlchemyUnitOfWork("sqlite+pysqlite:///:memory:")
CreateCurrency(uow)("USD", exchange_rate=Decimal("1"))
CreateCurrency(uow)("EUR", exchange_rate=Decimal("1.12"))
uow.currencies.set_base("USD")
CreateAccount(uow)("Assets:Cash", "USD")
CreateAccount(uow)("Assets:Cash:EUR", "EUR")
GetTradingBalanceDetailed(uow, clock)(base_currency="USD")
```

## 2. Жизненный цикл и транзакции

Паттерн: "Одна операция — один UnitOfWork".

1. Создать `uow = SqlAlchemyUnitOfWork(DATABASE_URL)`
2. Выполнить один или несколько use case'ов (должны относиться к одной бизнес-операции)
3. `uow.commit()` при успехе; `uow.rollback()` при исключении
4. Освободить ресурсы (опционально `uow.close()`), создать новый UoW для следующей операции

Не хранить UoW или внутренний `Session` глобально между потоками или запросами.

### Rollback
Любое необработанное исключение → `rollback()` перед повторным выбрасыванием или логированием.

## 3. Конкурентность и многопоточность

- Не шарить `SqlAlchemyUnitOfWork` / `Session` между потоками / корутинами.
- На каждый HTTP-запрос / команду бота / задачу из очереди — отдельный UoW.
- Держать транзакции короткими: не выполнять долгие сетевые операции, пока транзакция открыта.
- Для фоновых воркеров применить шаблон: `for task in queue: uow=...; try: use_case(); uow.commit(); except: uow.rollback()`.

## 4. Настройка окружения

Переменные окружения (рекомендация):
```
DATABASE_URL=postgresql+psycopg://user:pass@host:5432/dbname
LOG_LEVEL=INFO
JSON_LOGS=false
```

Для лёгких сценариев: `sqlite+pysqlite:///./local.db`.

Миграции (перед запуском приложения):
```bash
poetry run alembic upgrade head
```

Логирование:
```python
from infrastructure.logging.config import configure_logging, get_logger
configure_logging()  # на старте приложения
log = get_logger("integration")
log.info("started")
```

Переключение JSON режима — через `JSON_LOGS=true`.

## 5. Обслуживание / TTL

Команда очистки старых событий курсов:
```bash
poetry run python -m presentation.cli.main maintenance:fx-ttl --mode delete --retention-days 90 --json
```
Запускать отдельно (cron/systemd/Kubernetes CronJob), не в рамках обработчиков.

Рекомендации:
- Использовать `--batch-size` (если доступно) для деления работы
- Запуск в off-peak часы
- `--dry-run` для предварительной оценки

## 6. Пример интеграции: Telegram Bot

Папка `examples/telegram_bot` содержит рабочий пример.
Команды:
- `/start` — приветствие
- `/balance <account>` — баланс счёта
- `/tx <line1>;<line2>;...` — постинг транзакции (линия формат: `SIDE:Account:Amount:Currency`, пример: `DEBIT:Assets:Cash:100:USD`) две стороны обязательны
- `/rates` — список валют
- `/audit` — последние события курсов

UoW создаётся внутри каждого обработчика, commit после успешного use case.

## Telegram Bot (lean)

Пример лёгкой интеграции Telegram-бота, который использует текущие async use cases без дублирования доменной логики и без зависимости от aiogram. Все вызовы выполняются через асинхронный UoW; каждое обращение — отдельный UoW.

API регистрации обработчиков:
```
register_handlers(
    uow_factory: Callable[[], AsyncUnitOfWork],
    settings: Settings,
    clock: Clock | None = None,
) -> None
```
- uow_factory: фабрика нового AsyncSqlAlchemyUnitOfWork на каждый вызов
- settings: конфигурация примера
- clock: опционально; по умолчанию SystemClock (backward compatible)

Используемые async use cases:
- AsyncListCurrencies
- AsyncListExchangeRateEvents
- AsyncGetAccountBalance
- AsyncPostTransaction

Протокол работы:
- Команды — это функции-обработчики, доступные через `router["<cmd>"]`
- Вызов: `await router["rates"]()` или `await router["balance"]("Assets:Cash")`

Форматы ошибок (важно придерживаться при интеграции):
- Ошибки домена (ValueError) → `Error: <msg>`
- /tx: пустой payload или после парсинга пусто → `Error: No lines`
- /tx: ошибка формата строки → `Ошибка формата строки: line <i>: <reason>: <raw_line>`
- Неожиданные исключения → `Server error` (логирование вне примера)

Псевдокод интеграции с aiogram (без добавления зависимости):
```python
# settings, uow_factory как в примере
from examples.telegram_bot.handlers import register_handlers, router

register_handlers(uow_factory, settings)  # clock не передаём → SystemClock

async def on_message(text: str) -> str:
    # text, например: "/rates" или "/balance Assets:Cash"
    parts = (text or "").strip().split(maxsplit=1)
    if not parts:
        return "Commands: /start /rates /audit /balance /tx"
    cmd = parts[0].lstrip("/")
    payload = parts[1] if len(parts) > 1 else None
    handler = router.get(cmd)
    if not handler:
        return "Commands: /start /rates /audit /balance /tx"
    return await handler(payload)
```

Замечания по времени:
- Если нужен нестандартный источник времени, передайте `clock` в `register_handlers`
- По умолчанию используется `SystemClock`

Ссылки:
- README примера: `examples/telegram_bot/README.md`
- Хендлеры: `examples/telegram_bot/handlers.py`
- Инициализация: `examples/telegram_bot/app.py`

## 7. Пример интеграции: сервис-воркер / крон

```python
from infrastructure.persistence.sqlalchemy.uow import SqlAlchemyUnitOfWork
from application.use_cases.exchange_rates import UpdateExchangeRates
from application.dto.models import RateUpdateInput
from decimal import Decimal

db_url = "sqlite+pysqlite:///./example.db"
uow = SqlAlchemyUnitOfWork(db_url)
try:
    UpdateExchangeRates(uow)([RateUpdateInput(code="EUR", rate=Decimal("1.12"))])
    uow.commit()
except Exception:
    uow.rollback()
    raise
```

Периодический TTL:
```bash
poetry run python -m presentation.cli.main maintenance:fx-ttl --mode archive --retention-days 180 --json
```

## 8. FAQ / Траблшутинг

| Проблема | Причина | Решение |
|----------|---------|---------|
| Ошибки миграций | База не инициализирована | `alembic upgrade head` |
| Блокировки в Postgres | Долгие транзакции | Сократить обработку внутри commit-границы |
| SQLite locked | Параллельный доступ | Перейти на Postgres или serialize операции |
| Неверный баланс | Баланс-кэш не обновился | Использовать `RecalculateAccountBalance` или проверить commit |
| Таймзона | naive datetime | Использовать UTC-aware `clock.now()` |
| Decimal формат | Потеря точности в JSON | Сериализовать как строку |

## 9. Риски и ограничения

- SQLite не подходит для высокой конкурентности.
- Долгие транзакции → риск блокировок.
- Отказоустойчивость: при падении на середине операции — эффект частично выполненных команд; нужен чёткий commit/rollback.
- FX обновления: частые изменения курса могут увеличивать объём аудита (использовать TTL/архив).

## 10. Acceptance Criteria (NS21)

- Добавлен этот файл `docs/INTEGRATION_GUIDE.md`.
- Пример Telegram Bot работает (команды /start, /balance, /tx, /rates, /audit).
- Ядро не изменено, новых зависимостей нет в основном `pyproject.toml`.
- Документация включает жизненный цикл, транзакции, конфиги, конкурентность, TTL.
- Smoke: миграции + базовые команды CLI + запуск бота.

## 11. Smoke сценарии

```bash
# 1. Миграции
poetry run alembic upgrade head
# 2. Базовые сущности
poetry run python -m presentation.cli.main currency:add USD
poetry run python -m presentation.cli.main currency:set-base USD
poetry run python -m presentation.cli.main account:add Assets:Cash USD
# 3. Тест транзакции
poetry run python -m presentation.cli.main tx:post --line DEBIT:Assets:Cash:50:USD --line CREDIT:Assets:Cash:0:USD
# 4. Баланс
poetry run python -m presentation.cli.main balance:get Assets:Cash --json
# 5. TTL (при необходимости)
poetry run python -m presentation.cli.main maintenance:fx-ttl --mode delete --retention-days 90 --json
```

## 12. Дополнительно

- Веб-приложение: на каждый запрос новый UoW, сериализация Decimal → строка.
- Очереди (Rabbit/Kafka): один UoW на сообщение.
- Логи: `get_logger("integration")`, уровни INFO / WARNING / ERROR.

---
Документ поддерживается для версии 0.1.x.

## Примеры асинхронного использования

### 13. Пример асинхронной интеграции: веб-приложение

```python
import asyncio
from sqlalchemy import text
from infrastructure.persistence.sqlalchemy.uow import AsyncSqlAlchemyUnitOfWork

async def main():
    uow = AsyncSqlAlchemyUnitOfWork("sqlite+aiosqlite:///./example_async.db")
    async with uow.session_factory() as s:  # type: ignore[attr-defined]
        await s.execute(text("CREATE TABLE IF NOT EXISTS t (id INTEGER PRIMARY KEY, v TEXT)"))
        await s.commit()
    async with uow as _:
        await uow.session.execute(text("INSERT INTO t (v) VALUES ('hello')"))

asyncio.run(main())
```

### 14. Пример асинхронной интеграции: обёртка для синхронного кода

```python
from infrastructure.persistence.sqlalchemy.uow import AsyncSqlAlchemyUnitOfWork, SyncUnitOfWorkWrapper

wrapper = SyncUnitOfWorkWrapper(AsyncSqlAlchemyUnitOfWork("sqlite+aiosqlite:///./example_async.db"))
with wrapper:
    wrapper.commit()
    wrapper.rollback()
```

### 15. Async use cases (Application Layer)

Рекомендуемый путь для интеграции на async — использовать `AsyncUnitOfWork` и async use cases из `application.use_cases_async`.

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
)
from application.dto.models import EntryLineDTO

class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)

async def main() -> None:
    uow = AsyncSqlAlchemyUnitOfWork("sqlite+aiosqlite:///./example_async.db")
    async with uow:  # открываем транзакционную границу
        # Валюты
        await AsyncCreateCurrency(uow)("USD")
        await AsyncSetBaseCurrency(uow)("USD")
        # Счета
        await AsyncCreateAccount(uow)("Assets:Cash", "USD")
        # Транзакция
        lines = [
            EntryLineDTO("DEBIT", "Assets:Cash", Decimal("100"), "USD"),
            EntryLineDTO("CREDIT", "Assets:Cash", Decimal("100"), "USD"),
        ]
        await AsyncPostTransaction(uow, SystemClock())(lines, memo="Init")
        # Баланс
        bal = await AsyncGetAccountBalance(uow, SystemClock())("Assets:Cash")
        print("Balance:", bal)

asyncio.run(main())
```

Заметки:
- Все async use cases принимают `AsyncUnitOfWork` и используют только awaitable-методы репозиториев.
- Существующие sync use cases остаются для CLI/обратной совместимости (перенос в ASYNC-07).
- Методы list возвращают списки, параметры `meta` передаются прозрачно (можно `None` или `{}`).

## 16. Настройки пула, таймаутов и ретраев (ASYNC-09)

Добавлены переменные окружения для управления устойчивостью async-стека:

| Переменная | Назначение | Дефолт | Применимо |
|------------|-----------|--------|-----------|
| `DB_POOL_SIZE` | Базовый размер пула | 5 | PostgreSQL (asyncpg) |
| `DB_MAX_OVERFLOW` | Доп. соединения сверх пула | 10 | PostgreSQL |
| `DB_POOL_TIMEOUT` | Таймаут ожидания соединения (сек) | 30 | PostgreSQL |
| `DB_POOL_RECYCLE_SEC` | Рецикл (разрыв) соединения после сек | 1800 | PostgreSQL |
| `DB_CONNECT_TIMEOUT_SEC` | Таймаут установления соединения | 10 | PostgreSQL |
| `DB_STATEMENT_TIMEOUT_MS` | statement_timeout внутри транзакции | 0 (выключено) | PostgreSQL |
| `DB_RETRY_ATTEMPTS` | Кол-во попыток commit при транзистентных ошибках | 3 | Все |
| `DB_RETRY_BACKOFF_MS` | Начальный backoff между ретраями | 50 | Все |
| `DB_RETRY_MAX_BACKOFF_MS` | Верхняя граница backoff | 1000 | Все |

Поведение:
- Параметры пула и connect timeout применяются только к `postgresql+asyncpg`; для SQLite игнорируются без ошибок.
- `DB_STATEMENT_TIMEOUT_MS>0` приводит к выполнению `SET LOCAL statement_timeout = <ms>` при входе в транзакцию (только PostgreSQL). Ограничение действует до commit/rollback.
- Ретраи commit выполняются только для транзистентных ошибок: SQLSTATE `40001` (serialization failure), `40P01` (deadlock), либо `connection_invalidated` в исключении SQLAlchemy. Максимум `DB_RETRY_ATTEMPTS` попыток с экспоненциальным ростом задержки (минимум base, максимум cap).

Рекомендации:
- Для горизонтов 1–5 секунд операций используйте `DB_STATEMENT_TIMEOUT_MS=5000` чтобы избегать долгих блокировок.
- Наблюдайте метрики пула (conn. saturation) и при росте увеличивайте `DB_POOL_SIZE` / уменьшайте `DB_MAX_OVERFLOW` для предсказуемости.
- Не ставьте слишком короткий `DB_CONNECT_TIMEOUT_SEC` (<3) при нестабильной сети.

Пример `.env` для PostgreSQL продакшена:
```
DATABASE_URL=postgresql+psycopg://acc:pass@db:5432/ledger
DATABASE_URL_ASYNC=postgresql+asyncpg://acc:pass@db:5432/ledger
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=5
DB_POOL_TIMEOUT=30
DB_POOL_RECYCLE_SEC=1800
DB_CONNECT_TIMEOUT_SEC=10
DB_STATEMENT_TIMEOUT_MS=5000
DB_RETRY_ATTEMPTS=5
DB_RETRY_BACKOFF_MS=50
DB_RETRY_MAX_BACKOFF_MS=800
```

SQLite:
- Игнорирует настройки пула / statement timeout.
- Ретраи commit обычно не срабатыют, но механизм безвреден.

Диагностика:
- Логи `WARNING` уровня при ретраях содержат attempt, sqlstate (если доступен) и задержку.
- Если ретраи исчерпаны — выбрасывается исходное исключение.
