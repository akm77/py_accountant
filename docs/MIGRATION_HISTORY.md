# Migration History

## Цель
Зафиксировать эволюцию схемы БД и архитектурные изменения.

## Alembic ревизии
- 0001_initial — базовые таблицы: currencies, accounts, journals, transaction_lines, balances
- 0002_add_is_base_currency — поле `currencies.is_base`
- 0003_add_performance_indexes — индексы производительности
- 0004_add_exchange_rate_events — таблица exchange_rate_events + индексы code/occurred_at

## Удаление legacy py_fledger
- Статус: удалён (физически) — модуль и тесты parity к legacy больше не присутствуют.
- Date: 2025-11-10 (commit REF_PLACEHOLDER)
- Parity теперь работает только через expected-file (internal consistency).

## Parity переход
- Ранее: сравнение py_fledger.Book vs новые use cases.
- Сейчас: diagnostics:parity-report читает сценарии и сверяет с expected.

## ASYNC-01: Ввод async SQLAlchemy Engine (runtime)
- Дата: 2025-11-10
- Модуль: `src/infrastructure/persistence/sqlalchemy/async_engine.py`
- Функции: `normalize_async_url`, `get_async_engine`, `get_async_session_factory`
- Поведение: автоматическая нормализация sync URL -> async
  - `postgresql://` / `postgresql+psycopg://` -> `postgresql+asyncpg://`
  - `sqlite://` / `sqlite+pysqlite://` -> `sqlite+aiosqlite://`
- Поддерживаемые схемы (runtime): `postgresql+asyncpg://`, `sqlite+aiosqlite://`
- Alembic: остаётся на sync драйверах (`psycopg`/`pysqlite`) — разделение runtime vs migrations.
- Зависимости добавлены: `asyncpg`, `aiosqlite` (runtime), `pytest-asyncio` (dev).
- Тесты: `tests/unit/infrastructure/test_async_engine.py` — SQLite in-memory `SELECT 1`; опциональный Postgres smoke при наличии `DATABASE_URL` или `DATABASE_URL_ASYNC`.
- Гарантии: не изменяет существующий sync UoW/репозитории до итерации ASYNC-02.
- Следующие шаги: ASYNC-02 переведёт `SqlAlchemyUnitOfWork` на async контекстный менеджер; ASYNC-04 уточнит документацию по раздельным URL для Alembic/runtime.

## ASYNC-02: Async Unit of Work и sync-шимы (runtime)
- Дата: 2025-11-10
- Модуль: `src/infrastructure/persistence/sqlalchemy/uow.py`
- Добавлено:
  - `AsyncSqlAlchemyUnitOfWork` — async контекстный менеджер (`__aenter__/__aexit__`) с явными `commit/rollback/close`
  - `SyncUnitOfWorkWrapper` — синхронный мост к async UoW через `asyncio.run` с защитой от already-running loop
  - Legacy `SqlAlchemyUnitOfWork` сохранён без изменений для обратной совместимости
- Поведение:
  - Явное `begin()` в `__aenter__`; `commit` при успешном выходе, `rollback` при исключении; гарантированное закрытие `session`
  - Вызовы `commit/rollback` без активной сессии — no-op с предупреждением в логах
  - Повторный вход в один и тот же экземпляр UoW — `RuntimeError`
- Репозитории: остаются синхронными (перевод на async — ASYNC-03)
- URL: runtime — async (`postgresql+asyncpg://`, `sqlite+aiosqlite://`); Alembic — sync (`postgresql+psycopg://`, `sqlite+pysqlite://`)
- Тесты: `tests/unit/infrastructure/test_async_uow.py` — commit/rollback, wrapper-guard
- Гарантии: совместимость с существующими CLI и sync тестами
- Следующие шаги: ASYNC-03 — перевод SQLAlchemy-репозиториев на async API

## Async vs Sync URL

Разделение путей — ключ к безопасной эволюции:

| Контекст | Переменная | Пример значения | Драйвер | Назначение |
|----------|------------|-----------------|---------|------------|
| Runtime (async) | `DATABASE_URL_ASYNC` | `postgresql+asyncpg://u:p@h:5432/db` | asyncpg / aiosqlite | Использование в приложении (Async UoW, async engine) |
| Migrations (sync) | `DATABASE_URL` | `postgresql+psycopg://u:p@h:5432/db` | psycopg / pysqlite | Alembic миграции |

Принцип: Alembic не должен получать async драйвер. Если задан `DATABASE_URL=postgresql+asyncpg://...` или `sqlite+aiosqlite://...` — `alembic/env.py` падает с `RuntimeError("Async driver not supported for Alembic")`.

Порядок применения:
1. Выполнить миграции: `poetry run alembic upgrade head` (использует `DATABASE_URL`).
2. Запустить приложение / воркер: читает `DATABASE_URL_ASYNC` (или нормализует sync через `normalize_async_url`).

Fallback: Если `DATABASE_URL_ASYNC` отсутствует — runtime код может нормализовать `DATABASE_URL` к async виду, но миграции всегда читают именно sync.

WARNING: Никогда не вставлять `postgresql+asyncpg` или `sqlite+aiosqlite` в `alembic.ini` — это замедлит выявление ошибок в CI и может нарушить автогенерацию.

Smoke проверки (тесты):
- `test_sync_migrations_smoke` — успешный upgrade/downgrade на sync URL.
- `test_alembic_rejects_async_url` — отказ на async URL.
- `test_dual_url_consistency` — различие драйверов runtime vs migrations.
- `test_docs_sections_present` — наличие этого блока.

## Roadmap
- TTL/архив exchange_rate_events (NS20)
- FastAPI слой (NS18)
- Внешние FX провайдеры (NS17)

## I28: Deprecation of synchronous repositories
- Date: 2025-11-12
- Change: `src/infrastructure/persistence/sqlalchemy/repositories.py` заменён заглушками классов, каждый создаёт DeprecationWarning и RuntimeError.
- Motivation: закрепить async-only путь, исключить скрытое использование sync слоя перед физическим удалением.
- Migration: заменить любые импорты на async аналоги из `repositories_async.py`.
- Next: физическое удаление файла и обновление UoW (легаси sync) в последующих итерациях.
