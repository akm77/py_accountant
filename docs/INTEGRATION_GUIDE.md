```bash
# 1) Миграции
poetry run alembic upgrade head
# 2) Базовые операции выполняются через SDK (см. примеры ниже)
```

## Runtime vs Migration Database URLs (dual‑URL)

Для безопасного использования SQLAlchemy в проекте применяются два URL:

| Назначение | Переменная | Пример | Допустимые драйверы |
|------------|-----------|--------|---------------------|
| Миграции (Alembic) | `DATABASE_URL` / `PYACC__DATABASE_URL` | `postgresql+psycopg://user:pass@host:5432/db` | `postgresql`, `postgresql+psycopg`, `sqlite`, `sqlite+pysqlite` |
| Runtime (async) | `DATABASE_URL_ASYNC` / `PYACC__DATABASE_URL_ASYNC` | `postgresql+asyncpg://user:pass@host:5432/db` | `postgresql+asyncpg`, `sqlite+aiosqlite` |

Правила:
- Alembic читает только `DATABASE_URL` (или fallback из `alembic.ini`); async‑драйверы там запрещены.
- SDK использует `DATABASE_URL_ASYNC` (или `PYACC__DATABASE_URL_ASYNC`). При его отсутствии допускается нормализация sync URL (любого из ключей) в async.
- В CI шаг миграций использует sync URL; рантайм — async.
- См. также `docs/RUNNING_MIGRATIONS.md`.

Пример `.env`:
```
TELEGRAM_BOT_TOKEN=bot-token
BOT__SOME_SETTING=value
PYACC__DATABASE_URL=postgresql+psycopg://acc:pass@localhost:5432/ledger
PYACC__DATABASE_URL_ASYNC=postgresql+asyncpg://acc:pass@localhost:5432/ledger
PYACC__LOG_LEVEL=INFO
PYACC__LOGGING_ENABLED=true
```

Необязательные параметры logging/TTL также поддерживают двойное имя (`LOG_LEVEL` и `PYACC__LOG_LEVEL`).

Workflow:
```bash
poetry run alembic upgrade head   # читает DATABASE_URL или PYACC__DATABASE_URL
PYTHONPATH=src poetry run python -m examples.telegram_bot.app  # runtime async URL
```

### Отключение встроенного логгера SDK
- В инфраструктурном слое задайте `LOGGING_ENABLED=false` (или `PYACC__LOGGING_ENABLED=false`), чтобы SDK пропустил настройку structlog и позволил хост-приложению использовать собственный logger/handlers.
- Поведение UoW и use case'ов не меняется: `app.logger` остаётся доступным, но не имеет обработчиков, пока вы не настроите их самостоятельно.

## Использование как библиотеки (SDK)

SDK предоставляет стабильные импорты для интеграторов: `from py_accountant.sdk import bootstrap, use_cases, json, errors`.

### Инициализация
```python
from py_accountant.sdk import bootstrap
app = bootstrap.init_app()  # читает env, валидирует dual‑URL, создаёт uow_factory и UTC clock
# app.uow_factory(): Callable возвращающий AsyncSqlAlchemyUnitOfWork
# app.clock.now(): datetime в UTC
# app.settings: доступ к URL/параметрам
```

### Постинг транзакции (idempotency_key)
```python
from py_accountant.sdk import use_cases

async with app.uow_factory() as uow:
    tx = await use_cases.post_transaction(
        uow,
        app.clock,
        [
            "DEBIT:Assets:Cash:100:USD",
            "CREDIT:Income:Sales:100:USD",
        ],
        memo="Sale",
        meta={"idempotency_key": "order-42"},
    )
```

- Формат строки: `SIDE:Account:Amount:Currency[:Rate]` (Rate > 0 при небазовой валюте).
- Можно передавать готовые EntryLineDTO вместо строк.

### Баланс и выписка
```python
async with app.uow_factory() as uow:
    bal = await use_cases.get_account_balance(uow, app.clock, "Assets:Cash")
async with app.uow_factory() as uow:
    txs = await use_cases.get_ledger(
        uow,
        app.clock,
        "Assets:Cash",
        start=None,
        end=None,
        meta={},
        limit=50,
        order="DESC",
    )
```

### Trading raw/detailed
```python
from application.use_cases_async.trading_balance import (
    AsyncGetTradingBalanceRaw,
    AsyncGetTradingBalanceDetailed,
)
async with app.uow_factory() as uow:
    raw = await AsyncGetTradingBalanceRaw(uow, app.clock)()
async with app.uow_factory() as uow:
    det = await AsyncGetTradingBalanceDetailed(uow, app.clock)(base_currency="USD")
```

Пример (async):

```python
from application.use_cases_async.trading_balance import AsyncGetTradingBalanceDetailed

lines = await AsyncGetTradingBalanceDetailed(uow, clock)(base_currency="USD")
for l in lines:
    print(l.currency_code, l.net_base)
```

### TTL конфигурация (FX Audit)

Переменные окружения управляют политикой TTL:
- `FX_TTL_MODE` — `none|delete|archive` (по умолчанию `none`). Определяет, будут ли события удалены или архивированы.
- `FX_TTL_RETENTION_DAYS` — период хранения (>=0). Cutoff = `now() - retention_days` в UTC.
- `FX_TTL_BATCH_SIZE` — максимальный размер батча (`>0`, по умолчанию `1000`). Используется при построении плана.
- `FX_TTL_DRY_RUN` — логический флаг (`true|false`). При `true` исполнение пропускает мутации (без вызова `archive_events` и `delete_events_by_ids`).

Workflow (безопасный старт):
1. Установите `FX_TTL_MODE=archive`, `FX_TTL_DRY_RUN=true`, задайте `FX_TTL_RETENTION_DAYS=90`.
2. Выполните CLI `fx ttl-plan` и изучите `total_old`, `batches`, `old_event_ids`.
3. Запустите исполнение через воркер (SDK) с `FX_TTL_DRY_RUN=false`.
4. Мониторьте размеры архивной таблицы и длительность батчей.

Dry-run семантика: план возвращается полностью, но `AsyncExecuteFxAuditTTL` не вызывает примитивы мутации.

Dual-URL и TTL: миграции (sync URL) должны быть выполнены до запуска TTL-воркеров; runtime async URL используется планом и ис��олнением.

### TTL plan/execute (FX Audit)
```python
from application.use_cases_async.fx_audit_ttl import AsyncPlanFxAuditTTL, AsyncExecuteFxAuditTTL

async with app.uow_factory() as uow:
    plan = await AsyncPlanFxAuditTTL(uow, app.clock)(
        retention_days=90,
        batch_size=1000,
        mode="archive",  # none|delete|archive
        limit=None,
        dry_run=False,
    )
async with app.uow_factory() as uow:
    result = await AsyncExecuteFxAuditTTL(uow, app.clock)(plan)
```

### Единые форматы и сериализация
- Decimal → строка; datetime → ISO8601 UTC (допуск `Z` или `+00:00`).
- Квантизация: деньги — 2 знака, курсы — 6 знаков, ROUND_HALF_EVEN (см. `src/domain/quantize.py`).
- Презентер: `py_accountant.sdk.json.to_dict/to_json`.

### Ошибки и маппинг
- Используйте `py_accountant.sdk.errors.map_exception(exc)` для приведения внутренних ошибок к:
  - `UserInputError` (ValidationError/ValueError)
  - `DomainViolation` (DomainError)
  - `UnexpectedError` (иное)

## Форматы ввода/файлов (SDK)

- Строка проводки: `SIDE:Account:Amount:Currency[:Rate]` (пятый токен Rate опционален).
- SDK принимает строки в формате выше или готовые EntryLineDTO объекты.

## Ссылки
- См. «Шпаргалка проводок» — `docs/ACCOUNTING_CHEATSHEET.md`.
- См. «TRADING_WINDOWS.md» и «FX_AUDIT.md» для отчётов и TTL.

---
Документ согласован с кодом: `py_accountant/sdk/*`, `application/use_cases_async/*`, `domain/quantize.py`.
