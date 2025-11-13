# py-accountant

Чистая архитектура для бухгалтерского ядра на Python 3.13+ и SQLAlchemy 2.x. Слои: Domain / Application / Infrastructure / Presentation. Исторические детали см. в Migration History.

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

```bash
poetry install --with dev
poetry run alembic upgrade head
poetry run python -m presentation.cli.main currency add USD
poetry run python -m presentation.cli.main currency set-base USD
poetry run python -m presentation.cli.main currency add EUR --rate 1.123400
poetry run python -m presentation.cli.main account add Assets:Cash USD
poetry run python -m presentation.cli.main account add Income:Sales USD
poetry run python -m presentation.cli.main ledger post --line DEBIT:Assets:Cash:100:USD --line CREDIT:Income:Sales:100:USD --memo "Initial sale" --json
poetry run python -m presentation.cli.main ledger balance Assets:Cash --json
poetry run python -m presentation.cli.main trading raw --json
poetry run python -m presentation.cli.main trading detailed --base USD --json
poetry run python -m presentation.cli.main fx add-event EUR 1.123400 --json
poetry run python -m presentation.cli.main fx list --json
poetry run python -m presentation.cli.main fx ttl-plan --retention-days 0 --batch-size 10 --json
poetry run python -m presentation.cli.main diagnostics ping
```

## Архитектура слоёв

![Architecture Overview](docs/ARCHITECTURE_OVERVIEW.svg)

См. docs/ARCHITECTURE_OVERVIEW.md. Кратко:
- Domain — value-объекты, сервисы (балансы, политика курсов). Чистый слой.
- Application — DTO и use case'ы. Зависит от Domain; работает через порты.
- Infrastructure — адаптеры (SQLAlchemy, in-memory, Alembic, logging, settings).
- Presentation — CLI (API отложено).

Данные в JSON: Decimal → строка, datetime → ISO8601 UTC.

## Новое в CLI (итерации I-DX-01..I-DX-03, I-UX-01..02)
- `ledger post` поддерживает пятый токен `:Rate` в формате строки `SIDE:Account:Amount:Currency[:Rate]`.
- Опция `--occurred-at <ISO>` задаёт дату/время операции; naive → UTC.
- Загрузка строк из файла: `--lines-file <path.csv|json>` (CSV: `side,account,amount,currency[,rate]`; JSON: массив строк или объектов).
- Идемпотентный постинг: `--idempotency-key <key>` или `--meta idempotency_key=...` — повтор с тем же ключом возвращает прежний `tx.id` без дублей.
- Единый маппинг ошибок → дружелюбные сообщения; ожидаемые ошибки возвращают exit code 2.

Подробности и примеры см. `docs/CLI_QUICKSTART.md` и `docs/INTEGRATION_GUIDE.md`.

## FX Audit

См. docs/FX_AUDIT.md — таблицы exchange_rate_events + archive, индексы, политика хранения. В CLI доступны команды `fx add-event`, `fx list`, `fx ttl-plan` (только планирование TTL; выполнение — через SDK/use case).

## Trading Balance и окна времени

См. docs/TRADING_WINDOWS.md — семантика окна времени, примеры CLI, граничные случаи.

## Parity-report (внутренний инструмент)

См. docs/PARITY_REPORT.md — спецификация формата отчёта; публичной CLI-команды нет.

## Performance

См. docs/PERFORMANCE.md — формат отчёта JSON, инструкция запуска профиля и интерпретация полей.

## Migration History

См. docs/MIGRATION_HISTORY.md — ключевые шаги и удалённый код (историческая справка).

## Полезные ссылки
- docs/CLI_QUICKSTART.md
- docs/ARCHITECTURE_OVERVIEW.md
- docs/ARCHITECTURE_OVERVIEW.svg
- docs/FX_AUDIT.md
- docs/TRADING_WINDOWS.md
- docs/PARITY_REPORT.md
- docs/PERFORMANCE.md
- docs/RUNNING_MIGRATIONS.md
- docs/MIGRATION_HISTORY.md
- docs/INTEGRATION_GUIDE.md ← новый гайд по встраиванию
- examples/telegram_bot/README.md ← пример Telegram Bot

## Полностью асинхронное ядро

Синхронные репозитории и legacy sync UoW удалены в I29 (async-only завершён). Единственный поддерживаемый путь выполнения — async (CLI также async). Alembic по-прежнему использует sync драйверы только для миграций.
