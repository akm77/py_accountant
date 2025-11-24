# py-accountant

Чистая архитектура для бухгалтерского ядра на Python 3.13+ и SQLAlchemy 2.x. Слои: Domain / Application / Infrastructure. Исторические детали (включая старый SDK-слой) см. в Migration History.

- Язык: Python 3.13+
- ORM: SQLAlchemy 2.x
- Тесты: Pytest
- Линт/формат: Ruff
- Зависимости: Poetry

## Важное замечание про опубликованный пакет и локальную разработку

В репозитории хранится "core-only" реализация (Domain / Application / Infrastructure). В прошлом в пакете публиковался отдельный SDK-слой (`py_accountant.sdk.*`). На некоторых окружениях (например, в venv проектов, которые устанавливали старую версию) в `site-packages` может присутствовать установленный `py-accountant` с модулем `py_accountant.sdk` — это внешняя опубликованная версия пакета и она не обновляется автоматически из локального репозитория.

Если вы видите в traceback импорт из `.../site-packages/py_accountant/...` или в IDE — External Libraries — присутствует `py_accountant.sdk`, это означает, что интерпретатор использует установленную версию пакета, а не исходники из этого репозитория. В таком случае локальные изменения в `src/` не повлияют на импортируемый код.

Как убедиться, откуда импорт берётся:

```bash
# в каталоге проекта, где запускаете тесты (например tgbank):
poetry run python - <<'PY'
import py_accountant, inspect
print(py_accountant.__file__)
PY
```

Или посмотреть метаданные пакета:

```bash
poetry run pip show py_accountant
```

---

## Рекомендуемый рабочий процесс разработки (чтобы тесты использовали локальный core)

1) Лучший вариант — подключать локальную копию репозитория как path dependency в проекте интегратора (например в `tgbank`). В `pyproject.toml` интегратора добавьте:

```toml
[tool.poetry.dependencies]
py_accountant = { path = "../py_accountant", develop = true }
```

Затем в каталоге интегратора выполните:

```bash
poetry update py_accountant
poetry install
```

После этого интерпретатор и тесты будут импортировать вашу локальную версию (editable) и любые правки в исходниках будут видны сразу.

2) Временная опция — удалить установленный пакет из venv и запускать с PYTHONPATH указывающим на `src`:

```bash
cd /path/to/integrator
poetry run pip uninstall -y py_accountant
PYTHONPATH=/path/to/py_accountant/src poetry run pytest
```

3) Быстрая грязная хак-опция для локального теста: в `conftest.py` интегратора (ранний hook) вставьте `sys.path.insert(0, "/path/to/py_accountant/src")`. Это работает, но менее предпочтительно для долгосрочной работы.

---

## Контракты (реальные, на которые полагаются интеграторы)

Ниже — минимальная, реальная спецификация API/контрактов, которые ожидают use case'ы и интеграторы. Приведённые контракты отражают текущую реализацию в `application`/`application/use_cases_async` и `application/ports`.

1) UnitOfWork протоколы
- `UnitOfWork` (sync) — контекстный менеджер:
  - __enter__() -> UnitOfWork
  - __exit__(exc_type, exc, tb) -> None
  - свойства: `accounts`, `journals`, `exchange_rate_events`, ... — объекты-репозитории по контрактам из `application.ports`

- `AsyncUnitOfWork` (async) — асинхронный контекстный менеджер:
  - async def __aenter__(self) -> AsyncUnitOfWork
  - async def __aexit__(self, exc_type, exc, tb) -> None
  - свойства: `accounts`, `journals`, `exchange_rate_events`, ...

Репозитории предоставляют CRUD и примитивы, перечисленные в `application.ports` (например: `add`, `get_by_id`, `list`, `upsert_balance`, `list_old_events`, `archive_events` и т.д.).

2) Use case'ы — вызов и сигнатура
- Sync use cases (например `PostTransaction`, `GetBalance`) реализованы как вызываемые объекты: use_case(...) и возвращают значение напрямую.
- Async use cases (например `AsyncPostTransaction`, `AsyncGetAccountBalance`) — асинхронно вызываемые объекты: `await use_case(...)`.

Важно: некоторые интеграторы могли ожидать метода `execute()` у объекта use case. На текущей версии репозитория контракт — используйте вызов через `__call__` (sync) или `__call__` + `await` (async). Примеры:

Sync example:

```python
from py_accountant.application.use_cases.ledger import PostTransaction, GetBalance
from py_accountant.application.ports import UnitOfWork as UnitOfWorkProtocol


# sync context
with uow_factory() as uow:
    use_case = PostTransaction(uow, clock)
    result = use_case(lines=lines, memo=memo, meta=meta)
```

Async example:

```python
from py_accountant.application.use_cases_async.ledger import AsyncPostTransaction
from py_accountant.application.ports import AsyncUnitOfWork as AsyncUnitOfWorkProtocol


# async context
async with uow_factory() as uow:
    use_case = AsyncPostTransaction(uow, clock)
    tx = await use_case(lines=lines, memo=memo, meta=meta)
```

Если у вас падают тесты с ошибкой "'AsyncPostTransaction' object has no attribute 'execute'", замените вызовы `await use_case.execute(...)` на `await use_case(...)`.

---

## Интеграция через core (кратко)

Рекомендуемый способ использования — напрямую через слои Domain/Application и порты модуля `py_accountant.application.ports`. Async SDK‑слой больше не поставляется из этого репозитория; интеграция происходит напрямую через порты и use case'ы, как показано выше.

### Шаги для интегратора (tgbank пример)
1. Убедитесь, что в venv нет установленного старого пакета `py_accountant` (или используйте path dependency):

```bash
# проверить источник импорта
poetry run python - <<'PY'
import py_accountant
print(py_accountant.__file__)
PY
```

2. Если импорт идёт из `site-packages`, переключитесь на локальный код:
- Добавьте path dependency (рекомендуется) или
- `pip uninstall py_accountant` в окружении и используйте PYTHONPATH.

3. Исправьте фасады/обёртки, чтобы вызывать use case как callable, не через `.execute()`.

---

## Установка из GitHub (последовательности для разных целей)

### Для продакшена (фиксированная версия)
```bash
poetry add git+https://github.com/akm77/py_accountant.git@vX.Y.Z
```

### Для локальной разработки (рекомендуется)
В вашем интеграторе (например `tgbank`) используйте path dependency:

```toml
[tool.poetry.dependencies]
py_accountant = { path = "../py_accountant", develop = true }
```

Это гарантирует, что IDE и тесты будут использовать текущие исходники.

---

## ENV переменные: runtime async, миграции sync

ПОСЛЕ удаления SDK пространство имён `PYACC__` остаётся только как удобный префикс
для окружения, но никаких модулей `py_accountant.sdk.*` больше нет. Ядро
используется напрямую через слои Domain/Application и порты (`application.ports`).

Минимальный `.env` для работы ядра:

```
DATABASE_URL=sqlite+pysqlite:///./dev.db
DATABASE_URL_ASYNC=sqlite+aiosqlite:///./dev.db
LOG_LEVEL=DEBUG
LOGGING_ENABLED=true
```

`PYACC__*` можно продолжать использовать как алиасы (через pydantic-settings в
`infrastructure.config.settings`), но это деталь конкретного хоста.

## Configuration Environment Guide

### 1. Базовая структура `.env`
Рекомендуется хранить настройки бота и `py_accountant` в одном `.env`, используя префикс `PYACC__` для всех переменных SDK. Такой подход даёт два преимущества:
- визуально отделяет настройки интегратора от ядра бухгалтерии;
- упрощает передачу секретов в CI/CD (можно скопировать одну группу переменных).

Минимальный `.env`:
```
TELEGRAM_BOT_TOKEN=bot-token
BOT__RATE_LIMIT=10
PYACC__DATABASE_URL=sqlite+pysqlite:///./dev.db
PYACC__DATABASE_URL_ASYNC=sqlite+aiosqlite:///./dev.db
PYACC__LOG_LEVEL=DEBUG
PYACC__LOGGING_ENABLED=true
```

### 2. Карта переменных py_accountant
| Назначение | Переменная | Комментарии |
|------------|-----------|-------------|
| Sync URL для миграций | `DATABASE_URL` / `PYACC__DATABASE_URL` | Используется Alembic и любые sync-утилиты. Допустимы Postgres/SQLite sync драйверы. |
| Async URL рантайма | `DATABASE_URL_ASYNC` / `PYACC__DATABASE_URL_ASYNC` | Основной источник для Async UoW и инфраструктуры (`py_accountant.infrastructure.persistence.sqlalchemy.async_engine`). При отсутствии — нормализация из sync URL. |
| Уровень логов | `LOG_LEVEL` / `PYACC__LOG_LEVEL` | `DEBUG`, `INFO`, `WARNING`, ... |
| Формат логов | `JSON_LOGS` / `PYACC__JSON_LOGS` | `true` включает JSON + опциональный файл/ротацию. |
| Включение логгера | `LOGGING_ENABLED` / `PYACC__LOGGING_ENABLED` | `false` пропускает bootstrap логирования, если хост управляет логами сам. |
| TTL FX Audit | `FX_TTL_*` / `PYACC__FX_TTL_*` | `MODE`, `RETENTION_DAYS`, `BATCH_SIZE`, `DRY_RUN`. |
| Параметры БД (POOL, TIMEOUT, RETRY) | `DB_*` / `PYACC__DB_*` | Управляют async-пулом SQLAlchemy. |

### 3. Разделение переменных бота и SDK
- Используйте неймспейс `BOT__` или любой другой для собственных настроек. Пример: `BOT__ADMIN_CHAT_ID`, `BOT__PAYMENTS_URL`.
- В коде бота читайте обе группы: `os.getenv("TELEGRAM_BOT_TOKEN")` и `os.getenv("BOT__ADMIN_CHAT_ID")`. Модуль SDK автоматически найдёт `PYACC__*`.

### 4. Примеры конфигураций
#### Локальная разработка (SQLite)
```
PYACC__DATABASE_URL=sqlite+pysqlite:///./dev.db
PYACC__DATABASE_URL_ASYNC=sqlite+aiosqlite:///./dev.db
PYACC__LOG_LEVEL=DEBUG
PYACC__JSON_LOGS=false
PYACC__LOGGING_ENABLED=true
```
- Миграции: `poetry run alembic upgrade head`
- SDK-пример: `PYTHONPATH=src poetry run python -m examples.telegram_bot.app`

#### Продакшен (PostgreSQL + внешний логгер)
```
PYACC__DATABASE_URL=postgresql+psycopg://ledger:***@db:5432/ledger
PYACC__DATABASE_URL_ASYNC=postgresql+asyncpg://ledger:***@db:5432/ledger
PYACC__JSON_LOGS=true
PYACC__LOG_FILE=/var/log/py_accountant.json
PYACC__LOG_ROTATION=size
PYACC__LOG_MAX_BYTES=104857600
PYACC__LOGGING_ENABLED=false  # логирование делегировано оркестратору
```
- Перед запуском воркеров вызывайте `PYTHONPATH=src poetry run alembic upgrade head` в том же окружении.

### 5. Секреты и CI/CD
- В GitHub Actions/CI вынесите все `PYACC__*` в secrets/vars и прокидывайте через `env:` на шаги миграций и тестов.
- Для контейнеров используйте `.env` файл, смонтированный в compose/k8s Secret. Пример `docker-compose.yml`:
```yaml
services:
  bot:
    env_file:
      - ./.env
    environment:
      PYACC__LOGGING_ENABLED: "false"
```
- Никогда не коммитьте `.env` с реальными данными; храните пример в `docs/.env.example` (по желанию).

### 6. Траблшутинг
- Ошибка `ValueError: DATABASE_URL required` → проверьте, что хотя бы один из ключей (`DATABASE_URL` или `PYACC__DATABASE_URL`) присутствует и доступен процессу.
- Alembic читает только sync URL. Убедитесь, что runner, выполняющий миграции, загружает тот же `.env`.
- При `LOGGING_ENABLED=false` убедитесь, что хост-приложение добавляет собственные хендлеры, иначе сообщения SDK пропадут.
- Для смены БД без перезапуска обновите переменные и перезапустите процессы — настройки читаются при старте.

### 7. Быстрая проверка окружения
```bash
python - <<'PY'
import os
for key in sorted(k for k in os.environ if k.startswith('PYACC__')):
    print(f"{key}={os.environ[key]}")
PY
```
Команда помогает убедиться, что все `PYACC__` переменные доступны перед запуском миграций или бота.

---
Следующие разделы описывают исторический SDK-слой и архитектуру. Для актуальной интеграции используйте только импорты `py_accountant.*` и контракты из `py_accountant.application.ports` и `py_accountant.application.use_cases*`.

## Установка из GitHub

### Poetry
```bash
poetry add git+https://github.com/akm77/py_accountant.git
```

Poetry сохранит зависимость в `pyproject.toml` в разделе `[tool.poetry.dependencies]`. При необходимости используйте флаг `--branch`, `--tag` или `--rev` для закрепления на конкретной версии.

### pip
```bash
pip install "git+https://github.com/akm77/py_accountant.git"
```

Если проект использует `requirements.txt`, добавьте строку:
```
git+https://github.com/akm77/py_accountant.git
```
И выполните `pip install -r requirements.txt`. Для частных форков используйте SSH URL и настройте deploy key.

## Интеграция через core

Рекомендуемый способ использования — напрямую через слои Domain/Application и
порты (`application.ports`). Async SDK‑слой удалён, public API — это use case'ы
из `application.use_cases` и `application.use_cases_async`.

### 1. Подключение ядра в вашем проекте

```python
from application.use_cases.ledger import PostTransaction, GetBalance
from application.interfaces.ports import UnitOfWork  # legacy sync UnitOfWork protocol (preferred: use AsyncUnitOfWork from application.ports for async)


def post_deposit(uow_factory, clock, lines, meta):
    # uow_factory: Callable[[], UnitOfWork]
    with uow_factory() as uow:  # sync или async контекст в зависимости от реализации
        use_case = PostTransaction(uow, clock)
        # фактический контракт: __call__, а не execute
        return use_case(lines=lines, memo="Deposit", meta=meta)


def get_balance(uow_factory, clock, account_name: str):
    with uow_factory() as uow:
        use_case = GetBalance(uow, clock)
        return use_case(account_full_name=account_name)
```

Интегратор реализует свой `uow_factory` и репозитории по контрактам из
`application.ports`.

### 2. Реализация собственного UoW и репозиториев

```python
from collections.abc import Callable
from application.interfaces.ports import UnitOfWork as UnitOfWorkProtocol


class MyUnitOfWork(UnitOfWorkProtocol):
    def __enter__(self) -> "MyUnitOfWork":
        # открыть sync/async‑совместимую сессию, инициализировать репозитории
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        # commit/rollback и закрыть сессию
        ...

    # здесь реализуются свойства/репозитории, которые ожидают use case'ы


def make_uow_factory(url: str) -> Callable[[], UnitOfWorkProtocol]:
    def factory() -> UnitOfWorkProtocol:
        return MyUnitOfWork(url)

    return factory
```

### 3. Где искать use case'ы и порты

- Порты: `src/application/ports.py` (контракты UoW/репозиториев).
- Синхронные use case'ы (включая `PostTransaction`, `GetBalance`,
  `GetLedger`, `ListLedger`, `GetTradingBalanceRawDTOs`,
  `GetTradingBalanceDetailedDTOs`): `src/application/use_cases/ledger.py`.
- Async use case'ы (если вам нужен полностью async‑стек):
  `src/application/use_cases_async/*.py`.

Документация согласована с кодом: `application/use_cases/ledger.py`,
`application/use_cases_async/*`, `application/ports.py`.

## Архитектура слоёв

![Architecture Overview](docs/ARCHITECTURE_OVERVIEW.svg)

См. docs/ARCHITECTURE_OVERVIEW.md. Кратко:
- Domain — value-объекты, сервисы (балансы, политика курсов). Чистый слой.
- Application — DTO и use case'ы. Зависит от Domain; работает через порты.
- Infrastructure — адаптеры (SQLAlchemy, Alembic, logging, settings).

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

### Архитектура и концепции
- docs/ARCHITECTURE_OVERVIEW.md — архитектура Clean Architecture
- docs/ARCHITECTURE_OVERVIEW.svg — диаграмма слоёв
- docs/ACCOUNTING_CHEATSHEET.md — шпаргалка по проводкам
- docs/PERFORMANCE.md — производительность и оптимизации

### Интеграция
- **docs/INTEGRATION_GUIDE.md** — базовое руководство по встраиванию (core-only)
- **docs/INTEGRATION_GUIDE_AIOGRAM.md** — детальное руководство по интеграции в Telegram Bot (aiogram 3.x) ⭐
- examples/telegram_bot/ — рабочий пример бота с py_accountant

### Специализированные возможности
- docs/FX_AUDIT.md — аудит валютных операций
- docs/TRADING_WINDOWS.md — торговые окна и отчёты
- docs/PARITY_REPORT.md — отчёты о паритете

### Техническая документация
- docs/RUNNING_MIGRATIONS.md — работа с миграциями Alembic
- docs/MIGRATION_HISTORY.md — история изменений архитектуры

## Полностью асинхронное ядро

Слои Domain и Application предоставляют как sync, так и async use case'ы.
Async‑репозитории и `AsyncSqlAlchemyUnitOfWork` реализованы в инфраструктуре
(`infrastructure.persistence.sqlalchemy`). Публичный SDK‑слой больше не
поставляется; интеграция происходит напрямую через порты и use case'ы.

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
