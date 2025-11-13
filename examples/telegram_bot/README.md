# Telegram Bot (lean)

Короткий, самодостаточный пример интеграции Telegram-бота поверх текущих async use cases. Переход на SDK‑bootstrap упрощает инициализацию (uow_factory/clock/settings) и делает импорты стабильными.

## Доступные команды
- /start
- /rates
- /audit
- /balance
- /tx

## Требования
- Python 3.13+ (как в проекте)
- Poetry
- SQLite для быстрого старта

## Переменные окружения
Используются:
- TELEGRAM_BOT_TOKEN — заглушка для примера
- DATABASE_URL — sync URL (для миграций)
- DATABASE_URL_ASYNC — async URL (для runtime)
- AUDIT_LIMIT — необязательный лимит строк для /audit

Пример (macOS zsh):
```bash
export TELEGRAM_BOT_TOKEN="dummy-token"
export DATABASE_URL="sqlite:///dev.db"
export DATABASE_URL_ASYNC="sqlite+aiosqlite:///dev.db"
export AUDIT_LIMIT="10"
```

## Установка (Poetry)
```bash
cd /Users/admin/PycharmProjects/py_accountant
poetry install
```

## Миграции (sync URL)
Запускать из корня репозитория:
```bash
poetry run alembic upgrade head
```

## Пробный запуск примера
Точка входа инициализирует настройки/логирование/UoW через SDK и пишет лог `app_initialized` без реального бота:
```bash
poetry run python -m examples.telegram_bot.app
```

## Smoke-вызов хендлеров без aiogram
Вызов через встроенный router с DI. Работает с PYTHONPATH=src.
```bash
PYTHONPATH=src poetry run python - <<'PY'
import asyncio
from py_accountant.sdk import bootstrap
from examples.telegram_bot.handlers import register_handlers, router

async def main():
    app = bootstrap.init_app()
    register_handlers(app.uow_factory, app.settings)  # clock по умолчанию UTC
    print(await router["start"]())
    print(await router["rates"]())   # ожидаемо "No currencies defined" при пустой базе
    print(await router["audit"]())   # ожидаемо "No audit events" при пустой базе

asyncio.run(main())
PY
```

## Форматы ответов и ошибок
- /start → `Commands: /start /rates /audit /balance /tx`
- /rates → `No currencies defined` (если нет валют)
- /audit → `No audit events` (если нет событий)
- /balance Account:Full:Name
  - Без аргумента → `Usage: /balance <Account:Full:Name>`
  - Ошибка домена (ValueError) → `Error: <msg>`
  - Успех → `<full_name> balance=<decimal>`
- /tx <payload>
  - Пусто/после парсера пусто → `Error: No lines`
  - Ошибка формата строки → `Ошибка формата строки: line <i>: <reason>: <raw_line>`
  - Ошибка домена (ValueError) → `Error: <msg>`
  - Успех → `Transaction OK: tx:<uuidhex> (<n> lines)`

## DI и clock
Регистрация хендлеров:
```
register_handlers(uow_factory, settings, clock: Clock | None = None)
```
- uow_factory — Callable, возвращающий новый AsyncUnitOfWork на каждый вызов
- settings — объект Settings
- clock — опционален, по умолчанию SystemClock (backward compatible)

## Трюки и заметки
- Лимит для /audit задаётся через `AUDIT_LIMIT`.
- Пример не добавляет зависимость aiogram и не запускает реальный бот.

## Тестирование
- Полный прогон тестов репозитория:
```bash
cd /Users/admin/PycharmProjects/py_accountant
poetry run pytest -q
```
- Для проверки только примера достаточно smoke-вызовов из раздела выше.

## Траблшутинг
- Alembic должен запускаться из корня репозитория; используется `DATABASE_URL` (sync).
- Если импортов не видно, добавьте `PYTHONPATH=src` перед командой Python.
