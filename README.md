# py-accountant

Чистая архитектура для бухгалтерского ядра на Python 3.13+ и SQLAlchemy 2.x. Слои: Domain / Application / Infrastructure. Исторические детали см. в Migration History.

- Язык: Python 3.13+
- ORM: SQLAlchemy 2.x
- Тесты: Pytest
- Линт/формат: Ruff
- Зависимости: Poetry

## ENV переменные: runtime async, миграции sync

- DATABASE_URL — синхронный URL для Alembic миграций (пример: `postgresql+psycopg://...`, `sqlite+pysqlite:///./dev.db`).
- DATABASE_URL_ASYNC — асинхронный URL для рантайма (пример: `postgresql+asyncpg://...`, `sqlite+aiosqlite://...`).

Порядок:
- Перед запуском приложения выполните миграции: `poetry run alembic upgrade head` (читает DATABASE_URL).
- Приложение/воркеры используют DATABASE_URL_ASYNC. Если он не задан — код рантайма нормализует DATABASE_URL в async.

## Quick Start


## SDK surface

Над существующими async use cases добавлен тонкий стабильный SDK-слой: `py_accountant.sdk`.
Ключевые модули: `bootstrap`, `use_cases`, `json`, `errors`, `settings`, `uow`.

Минимальный рабочий пример (инициализация + постинг с idempotency_key + баланс/ledger):

```python
import asyncio
from py_accountant.sdk import bootstrap, use_cases, json as sdk_json

async def main():
    app = bootstrap.init_app()  # читает .env, валидирует dual-URL
    # 1) Постинг транзакции (две строки)
    async with app.uow_factory() as uow:
        tx = await use_cases.post_transaction(
            uow,
            app.clock,
            [
                "DEBIT:Assets:Cash:100:USD",
                "CREDIT:Income:Sales:100:USD",
            ],
            memo="Init",
            meta={"idempotency_key": "demo-001"},
        )
    print("TX:", sdk_json.to_json(tx))

    # 2) Баланс счёта
    async with app.uow_factory() as uow:
        bal = await use_cases.get_account_balance(uow, app.clock, "Assets:Cash")
    print("BAL:", sdk_json.to_json({"account": "Assets:Cash", "balance": bal}))

    # 3) Выписка по счёту (короткая форма)
    async with app.uow_factory() as uow:
        items = await use_cases.get_ledger(uow, app.clock, "Assets:Cash", limit=5, order="DESC")
    print("LEDGER items:", len(items))

asyncio.run(main())
```

- Trading Detailed и TTL (plan/execute): выполняются через существующие use case’ы внутри `async with app.uow_factory(): ...` (см. подробности в docs/INTEGRATION_GUIDE.md).
- Согласованные форматы: Decimal → строка; datetime → ISO8601 UTC (`Z`/`+00:00`).
- Маппинг ошибок: используйте `py_accountant.sdk.errors.map_exception()` для дружелюбных сообщений.
- Fast-path баланса: `use_cases.get_account_balance()` делегирует в AsyncGetAccountBalance, который при `as_of=None` читает денормализованный остаток из `account_balances` (O(1)); для исторических дат выполняется безопасный fallback к сканированию леджера.
- Периодные обороты (SDK): `py_accountant.sdk.reports.turnover.get_account_daily_turnovers()` читает агрегаты `account_daily_turnovers` и возвращает списки дневных дебет/кредит/нетто по счёту/всем счетам без сканирования журнала.

Подробн��е: см. `docs/INTEGRATION_GUIDE.md` (раздел «Использование как библиотеки (SDK)») и «Шпаргалку проводок» `docs/ACCOUNTING_CHEATSHEET.md`.

## Архитектура слоёв

![Architecture Overview](docs/ARCHITECTURE_OVERVIEW.svg)

См. docs/ARCHITECTURE_OVERVIEW.md. Кратко:
- Domain — value-объекты, сервисы (балансы, политика курсов). Чистый слой.
- Application — DTO и use case'ы. Зависит от Domain; работает через порты.
- Infrastructure — адаптеры (SQLAlchemy, in-memory, Alembic, logging, settings).
- SDK — публичный интерфейс для использования как библиотеки (bootstrap, use_cases, json, errors).

Данные в JSON: Decimal → строка, datetime → ISO8601 UTC.


## FX Audit TTL (кратко)

Репозитории FX Audit теперь строго CRUD + примитивы TTL (`list_old_events`, `archive_events`, `delete_events_by_ids`). Оркестрация TTL вынесена в домен (`FxAuditTTLService`) и async use cases (`AsyncPlanFxAuditTTL`, `AsyncExecuteFxAuditTTL`). Исполнение выполняется воркером/SDK. Подробнее: `docs/FX_AUDIT.md` и раздел TTL в `docs/INTEGRATION_GUIDE.md`.

## FX Audit

См. docs/FX_AUDIT.md — таблицы exchange_rate_events + archive, индексы, политика хранения. Используйте SDK для работы с событиями курсов и TTL.

## Trading Balance и окна времени

См. docs/TRADING_WINDOWS.md — семантика окна времени, примеры использования SDK, граничные случаи.

## Parity-report (внутренний инструмент)

См. docs/PARITY_REPORT.md — спецификация формата отчёта; доступ только через SDK/use cases.

## Performance

См. docs/PERFORMANCE.md — формат отчёта JSON, инструкция запуска профиля и интерпретация полей.

## Migration History

См. docs/MIGRATION_HISTORY.md — ключевые шаги и удалённый код (историческая справка).

## Полезные ссылки
- docs/ARCHITECTURE_OVERVIEW.md
- docs/ARCHITECTURE_OVERVIEW.svg
- docs/FX_AUDIT.md
- docs/TRADING_WINDOWS.md
- docs/PARITY_REPORT.md
- docs/PERFORMANCE.md
- docs/RUNNING_MIGRATIONS.md
- docs/MIGRATION_HISTORY.md
- docs/INTEGRATION_GUIDE.md ← гид по встраиванию (SDK)
- docs/ACCOUNTING_CHEATSHEET.md ← шпаргалка по проводкам
- examples/telegram_bot/README.md ← пример Telegram Bot

## Полностью асинхронное ядро

Синхронные репозитории и legacy sync UoW удалены в I29 (async-only завершён). Единственный поддерживаемый путь выполнения — async через SDK. Alembic по-прежнему использует sync драйверы только для миграций.

## Fast balance & turnover (denormalized aggregates)

Для ускорения получения текущего баланса и отчётов по оборотам введены две денормализованные таблицы (initiative I31):
- account_balances: O(1) чтение текущего остатка счёта (balance += Δ для каждой проводки).
- account_daily_turnovers: агрегированные дневные суммы debit_total / credit_total для быстрого построения оборотно-сальдовой ведомости.

Механика:
1. Постинг транзакции вставляет journal + строки.
2. В той же транзакции вычисляется Δ (DEBIT=+, CREDIT=-) per account и выполняется UPSERT в account_balances.
3. Группировка по (account_full_name, day UTC) агрегирует дебет/кредит и делает UPSERT в account_daily_turnovers.
4. Commit фиксирует и журнал, и агрегаты атомарно.

Fast-path AsyncGetAccountBalance:
- Если as_of отсутствует (текущий момент) → читает из account_balances, при отсутствии строки возвращает Decimal('0').
- Если требуется исторический момент (as_of < now) и snapshots ещё не реализованы → fallback к сканированию строк (DEBIT-CREDIT).

Concurrency & Idempotency:
- Одновременные постинги безопасны (один txn scope + пошаговые SELECT+INSERT/UPDATE).
- Idempotency key в journals гарантирует, что повторный постинг не изменит агрегаты.

Edge cases:
- Новый счёт без строк → отсутствует запись в account_balances → баланс = 0.
- Проводки с нулевыми суммами можно оптимизационно пропускать (в текущей версии просто дадут Δ=0).

Future:
- account_balance_snapshots (EOD) для быстрого исторического баланса без полного скана.
