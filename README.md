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
poetry run python -m presentation.cli.main currency:add USD
poetry run python -m presentation.cli.main currency:set-base USD
poetry run python -m presentation.cli.main currency:add EUR
poetry run python -m presentation.cli.main fx:update EUR 1.1111
poetry run python -m presentation.cli.main fx:update EUR 1.1234
poetry run python -m presentation.cli.main diagnostics:rates-audit --json
poetry run python -m presentation.cli.main account:add Assets:Cash USD
poetry run python -m presentation.cli.main account:add Income:Sales USD
poetry run python -m presentation.cli.main tx:post --line DEBIT:Assets:Cash:100:USD --line CREDIT:Income:Sales:100:USD
poetry run python -m presentation.cli.main trading:detailed --base USD --json
poetry run python -m presentation.cli.main diagnostics:parity-report --expected-file examples/expected_parity.json --json
poetry run pytest -q tests/docs
```

## Архитектура слоёв

См. docs/ARCHITECTURE_OVERVIEW.md. Кратко:
- Domain — value-объекты, сервисы (балансы, политика курсов). Чистый слой.
- Application — DTO и use case'ы. Зависит от Domain; работает через порты.
- Infrastructure — адаптеры (SQLAlchemy, in-memory, Alembic, logging, settings).
- Presentation — CLI (API отложено).

Данные в JSON: Decimal → строка, datetime → ISO8601 с Z.

## FX Audit

См. docs/FX_AUDIT.md — таблица exchange_rate_events, индексы, примеры вывода diagnostics:rates-audit, политика хранения.

## Trading Balance и окна времени

См. docs/TRADING_WINDOWS.md — семантика окна времени, примеры CLI, граничные случаи.

## Parity-report (без legacy)

Команда diagnostics:parity-report сравнивает текущий движок с ожидаемым JSON из expected-file. Если expected не передан — сценарии помечаются как skipped. Формат ожидаемого и отчёта — см. docs/PARITY_REPORT.md.

Короткий прогон:
```bash
poetry run python -m presentation.cli.main diagnostics:parity-report --expected-file examples/expected_parity.json --json
```

## Performance

См. docs/PERFORMANCE.md — формат отчёта JSON, инструкция запуска профиля и интерпретация полей.

## Migration History

См. docs/MIGRATION_HISTORY.md — ключевые шаги и удалённый код (историческая справка).

## Roadmap

- NS13: done — Parity internal consistency, примеры expected
- NS15: done — Trading windows CLI/документация
- NS16: done — FX Audit events + диагностика
- NS17: Внешние FX провайдеры (адаптеры + health)
- NS18: FastAPI слой
- NS19: Экспорт отчётов (CSV/JSON)
- NS20: TTL/архивация exchange_rate_events
- NS21: done — Интеграция (SDK паттерны, Telegram Bot пример, docs/INTEGRATION_GUIDE.md)

## Полезные ссылки
- docs/CLI_QUICKSTART.md
- docs/ARCHITECTURE_OVERVIEW.md
- docs/FX_AUDIT.md
- docs/TRADING_WINDOWS.md
- docs/PARITY_REPORT.md
- docs/PERFORMANCE.md
- docs/MIGRATION_HISTORY.md
- docs/INTEGRATION_GUIDE.md ← новый гайд по встраиванию
- examples/telegram_bot/README.md ← пример Telegram Bot

## Полностью асинхронное ядро

Синхронные репозитории и legacy sync UoW удалены в I29 (async-only завершён). Единственный поддерживаемый путь выполнения — async (CLI также async). Alembic по-прежнему использует sync драйверы только для миграций.
