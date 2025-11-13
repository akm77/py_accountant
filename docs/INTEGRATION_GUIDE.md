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

## Runtime vs Migration Database URLs (dual‑URL)

Для безопасного использования SQLAlchemy в проекте применяются два URL:

| Назначение | Переменная | Пример | Допустимые драйверы |
|------------|-----------|--------|---------------------|
| Миграции (Alembic) | `DATABASE_URL` | `postgresql+psycopg://user:pass@host:5432/db` | `postgresql`, `postgresql+psycopg`, `sqlite`, `sqlite+pysqlite` |
| Runtime (async) | `DATABASE_URL_ASYNC` | `postgresql+asyncpg://user:pass@host:5432/db` | `postgresql+asyncpg`, `sqlite+aiosqlite` |

Правила:
- Alembic читает только `DATABASE_URL` (или fallback из `alembic.ini`); async‑драйверы там запрещены.
- Приложение, CLI и SDK используют `DATABASE_URL_ASYNC`. При его отсутствии допускается нормализация sync URL в async.
- В CI шаг миграций использует sync URL; рантайм — async.
- См. также `docs/RUNNING_MIGRATIONS.md`.

Пример `.env`:
```
DATABASE_URL=postgresql+psycopg://acc:pass@localhost:5432/ledger
DATABASE_URL_ASYNC=postgresql+asyncpg://acc:pass@localhost:5432/ledger
LOG_LEVEL=INFO
```

Workflow:
```bash
poetry run alembic upgrade head   # sync URL
poetry run python -m presentation.cli.main trading detailed --base USD  # runtime async URL
```

WARNING: Не прописывайте async URL в `alembic.ini` — потеряется защита.

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

### CLI vs SDK
- CLI покрывает большинство операций, включая TTL планирование.
- Выполнение TTL (execute) доступно через SDK/use case’ы в ваших воркерах/cron.

## Форматы ввода/файлов (CLI/SDK)

- Строка проводки: `SIDE:Account:Amount:Currency[:Rate]` (поддерживаются вложенные `:` в Account в CLI-парсере).
- Файлы для `--lines-file`:
  - CSV: заголовки `side,account,amount,currency[,rate]`.
  - JSON: массив строк в формате выше или объектов `{side,account,amount,currency[,rate]}`.

## Ссылки
- См. «Шпаргалка проводок» — `docs/ACCOUNTING_CHEATSHEET.md`.
- См. «TRADING_WINDOWS.md» и «FX_AUDIT.md» для отчётов и TTL.

---
Документ согласован с кодом: `py_accountant/sdk/*`, `presentation/cli/*`, `application/use_cases_async/*`, `domain/quantize.py`.
