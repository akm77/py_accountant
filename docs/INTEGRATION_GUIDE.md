```markdown
```bash
# 1) Миграции
poetry run alembic upgrade head
# 2) Базовые операции выполняются через core (`py_accountant.*`, см. примеры ниже)
```

## Runtime vs Migration Database URLs (dual‑URL)

Для безопасного использования SQLAlchemy в проекте применяются два URL:

| Назначение | Переменная | Пример | Допустимые драйверы |
|------------|-----------|--------|---------------------|
| Миграции (Alembic) | `DATABASE_URL` / `PYACC__DATABASE_URL` | `postgresql+psycopg://user:pass@host:5432/db` | `postgresql`, `postgresql+psycopg`, `sqlite`, `sqlite+pysqlite` |
| Runtime (async) | `DATABASE_URL_ASYNC` / `PYACC__DATABASE_URL_ASYNC` | `postgresql+asyncpg://user:pass@host:5432/db` | `postgresql+asyncpg`, `sqlite+aiosqlite` |

Правила:
- Alembic читает только `DATABASE_URL` (или fallback из `alembic.ini`); async‑драйверы там запрещены.
- Инфраструктурный слой (`py_accountant.infrastructure.persistence.sqlalchemy.*` и `AsyncSqlAlchemyUnitOfWork`) использует `DATABASE_URL_ASYNC` (или `PYACC__DATABASE_URL_ASYNC`). При его отсутствии допускается нормализация sync URL (любого из ключей) в async.
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

## Использование как библиотеки (core-only)

Интеграция осуществляется напрямую через use case'ы и порты модуля `py_accountant.application`, без отдельного SDK‑обёртки. Во внешних проектах используйте только импорты вида `py_accountant.*`.

### 1. Зависимость

```bash
poetry add git+https://github.com/akm77/py_accountant.git
# или
pip install "git+https://github.com/akm77/py_accountant.git"
```

### 2. Реализация собственного UoW

```python
from collections.abc import Callable
from py_accountant.application.ports import UnitOfWork as UnitOfWorkProtocol


class MyUnitOfWork(UnitOfWorkProtocol):
    def __enter__(self) -> "MyUnitOfWork":
        # открыть сессию/подключение, инициализировать репозитории
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        # commit/rollback и закрыть сессию
        ...

    # свойства/репозитории, которые ожидают use case'ы


def make_uow_factory(url: str) -> Callable[[], UnitOfWorkProtocol]:
    def factory() -> UnitOfWorkProtocol:
        return MyUnitOfWork(url)

    return factory
```

### 3. Вызов use case'ов ledger

```python
from py_accountant.application.use_cases.ledger import PostTransaction, GetBalance


def post_deposit(uow_factory, clock, account: str, amount, currency: str, meta: dict):
    lines = [
        # Заполните EntryLineDTO по своим правилам маппинга
    ]
    with uow_factory() as uow:
        use_case = PostTransaction(uow, clock)
        return use_case(lines=lines, memo="Deposit", meta=meta)


def get_balance(uow_factory, clock, account: str):
    with uow_factory() as uow:
        use_case = GetBalance(uow, clock)
        return use_case(account_full_name=account)
```

### 4. Где искать контракты

- Порты: `py_accountant.application.ports`.
- Use case'ы (sync): `py_accountant.application.use_cases.*`.
- Use case'ы (async): `py_accountant.application.use_cases_async.*`.

Документ согласован с кодом: `src/py_accountant/application/use_cases/ledger.py`,
`src/py_accountant/application/use_cases_async/*`, `src/py_accountant/application/ports.py`.

---

## Детальные примеры интеграции

Для подробных пошаговых руководств по интеграции в конкретные фреймворки см.:

- **[INTEGRATION_GUIDE_AIOGRAM.md](INTEGRATION_GUIDE_AIOGRAM.md)** — Полное руководство по интеграции в Telegram Bot на aiogram 3.x
  - Структура проекта и зависимости
  - UnitOfWork и Clock адаптеры
  - Маппинг команд на use cases
  - Dependency Injection через middlewares
  - Error handling и логирование
  - CI/CD, Docker, миграции в production
  - Тестирование (unit, integration, e2e)
  - Production checklist с мониторингом и безопасностью

