# RUNNING_MIGRATIONS

> Helper-документ для запуска Alembic миграций в CI/CD и локально. Цель: гарантировать безопасное разделение синхронного пути миграций и асинхронного runtime.

## 1. Ключевой принцип

Миграции всегда выполняются на SYNCHRONOUS драйвере.

Runtime (приложение, воркеры, async UoW) используют ASYNC драйвер.

| Контекст | Переменная | Пример | Допустимые драйверы |
|----------|-----------|--------|---------------------|
| Alembic (миграции) | `DATABASE_URL` | `postgresql+psycopg://user:pass@host:5432/db` | `postgresql`, `postgresql+psycopg`, `postgresql+psycopg2`, `sqlite`, `sqlite+pysqlite` |
| Runtime (async) | `DATABASE_URL_ASYNC` | `postgresql+asyncpg://user:pass@host:5432/db` | `postgresql+asyncpg`, `sqlite+aiosqlite` |

Alembic игнорирует `DATABASE_URL_ASYNC` и выбрасывает `RuntimeError` при попытке использовать async драйвер (`asyncpg` / `aiosqlite`).

## 2. Порядок запуска (Workflow)

1. Экспортировать/установить `DATABASE_URL` (sync).
2. Выполнить миграции: `poetry run alembic upgrade head`.
3. Запустить приложение, которое читает `DATABASE_URL_ASYNC` (или нормализует `DATABASE_URL`).

## 3. GitHub Actions пример

```yaml
name: migrations
on: [push]
jobs:
  alembic:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_USER: acc
          POSTGRES_PASSWORD: acc
          POSTGRES_DB: ledger
        ports: ["5432:5432"]
        options: >-
          --health-cmd "pg_isready -U acc" --health-interval 5s --health-timeout 5s --health-retries 10
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.13'
      - name: Install poetry
        run: pip install poetry
      - name: Install deps
        run: poetry install --with dev
      - name: Run migrations (sync URL)
        env:
          DATABASE_URL: postgresql+psycopg://acc:acc@localhost:5432/ledger
        run: poetry run alembic upgrade head
```

## 4. GitLab CI пример

```yaml
stages: [migrate]
migrate:
  stage: migrate
  image: python:3.13
  services:
    - name: postgres:16
      alias: db
  variables:
    POSTGRES_USER: acc
    POSTGRES_PASSWORD: acc
    POSTGRES_DB: ledger
  before_script:
    - pip install poetry
    - poetry install --with dev
  script:
    - export DATABASE_URL="postgresql+psycopg://acc:acc@db:5432/ledger"
    - poetry run alembic upgrade head
```

## 5. Локальная разработка

```bash
# Инициализация

export DATABASE_URL=sqlite+pysqlite:///./dev.db
poetry run alembic upgrade head
# Запуск приложения (если есть async runtime)
export DATABASE_URL_ASYNC=sqlite+aiosqlite:///./dev.db
poetry run python -m presentation.cli.main trading detailed --base USD
```

## 6. Проверка на misconfiguration

Быстрая Python проверка (можно встроить в CI):

```python
import os
from sqlalchemy.engine import make_url

sync_url = os.getenv("DATABASE_URL")
async_url = os.getenv("DATABASE_URL_ASYNC")
assert sync_url, "Missing DATABASE_URL"
sync_driver = make_url(sync_url).drivername
assert "async" not in sync_driver and "aiosqlite" not in sync_driver, f"Alembic must not use async driver: {sync_driver}"
if async_url:
    async_driver = make_url(async_url).drivername
    assert async_driver != sync_driver, "Async and sync URLs should differ by driver segment"
    assert any(x in async_driver for x in ["asyncpg", "aiosqlite"]), f"Runtime async driver not detected: {async_driver}"
print("Migration URL OK; runtime URL OK")
```

## 7. Типичные ошибки

| Ошибка | Причина | Решение |
|--------|---------|---------|
| `RuntimeError: Async driver not supported for Alembic` | В `DATABASE_URL` указан async драйвер | Указать sync драйвер (`postgresql+psycopg://` или `sqlite+pysqlite://`) |
| `ValueError: No synchronous database URL found` | Отсутствует переменная и запись в alembic.ini | Экспортировать `DATABASE_URL` или прописать в `alembic.ini` |
| Одинаковые driver части в обоих URL | Неправильная конфигурация runtime | Установить `DATABASE_URL_ASYNC` с async драйвером |
| Миграции молча прошли с async URL | ��еверная версия env.py (без проверки) | Обновить проект до версии с get_sync_url() |

## 8. Checklist для CI

- [ ] Установлен sync `DATABASE_URL`
- [ ] Не задан async драйвер в `DATABASE_URL`
- [ ] (Опционально) установлен `DATABASE_URL_ASYNC` с async драйвером
- [ ] Выполнен `alembic upgrade head`
- [ ] Сценарии тестов не подменяют миграционный URL на async
- [ ] Документ `RUNNING_MIGRATIONS.md` в репозитории (смoke-проверка)

## 9. FAQ

**Можно ли использовать только один URL?** Да, если runtime код нормализует sync URL в async, но предпочтительнее два явных переменных для прозрачности.

**Почему нельзя async для миграций?** Alembic не гарантирует стабильную работу и инструменты автогенерации ориентированы на sync Engine.

**Нужно ли указывать пароль в CI логах?** Нет — используйте masked secrets.

**Как откатить миграции?** `poetry run alembic downgrade base` (или до нужного revision id).

## 10. Связанные документы

- `docs/MIGRATION_HISTORY.md` — исторический контекст и раздел "Async vs Sync URL"
- `docs/INTEGRATION_GUIDE.md` — секция "Runtime vs Migration Database URLs"
- `README.md` — краткое перечисление переменных окружения

---
Поддерживается в рамках итерации ASYNC-04.
