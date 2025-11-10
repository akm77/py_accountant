# Telegram Bot Example

Пример интеграции `py-accountant` как библиотеки.

## Функциональность
- `/start` приветствие
- `/balance <account>` баланс счёта
- `/tx <line1>;<line2>;...` постинг транзакции (минимум 2 линии)
- `/rates` список валют
- `/audit` последние события курсов

## Подготовка
```bash
export DATABASE_URL=sqlite+pysqlite:///./bot.db
poetry run alembic upgrade head
# базовая валюта и аккаунт
poetry run python -m presentation.cli.main currency:add USD
poetry run python -m presentation.cli.main currency:set-base USD
poetry run python -m presentation.cli.main account:add Assets:Cash USD
```

## Зависимости примера (НЕ добавляются в основной pyproject)
```bash
pip install python-telegram-bot==21.*
```

## Запуск
```bash
export BOT_TOKEN=123:ABCDEF_TOKEN
export DATABASE_URL=sqlite+pysqlite:///./bot.db
python examples/telegram_bot/app.py
```

## Формат `/tx`
```
/tx DEBIT:Assets:Cash:100:USD;CREDIT:Assets:Cash:0:USD
```

Каждая линия: `SIDE:AccountFullName:Amount:CurrencyCode`.

## Ошибки
При бизнес-ошибках (`DomainError`) бот отвечает сообщением с причиной.

## Логи
Использует `get_logger("bot")`. Настройки через ENV: `LOG_LEVEL`, `JSON_LOGS`.

## Безопасность
- Не хранить токен в репозитории
- Ограничить доступ к SQL файлу для sqlite

## Завершение
Ctrl+C — корректное завершение.

