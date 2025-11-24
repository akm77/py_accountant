# Telegram Bot Integration Example

Этот пример демонстрирует интеграцию `py_accountant` в телеграм-бот для управления личными финансами.

## Структура

```
examples/telegram_bot/
├── README.md           # Этот файл
├── config.py           # Конфигурация приложения
├── main.py             # Entry point
├── uow.py              # UnitOfWork factory
├── clock.py            # Clock provider
├── handlers/
│   ├── __init__.py
│   ├── transaction.py  # /deposit, /expense
│   ├── account.py      # /balance, /accounts
│   ├── currency.py     # /currencies, /set_base
│   └── history.py      # /history
├── middlewares/
│   ├── __init__.py
│   ├── uow.py          # UoW injection middleware
│   ├── clock.py        # Clock injection middleware
│   ├── error_handler.py # Error handling middleware
│   └── logging.py      # Logging context middleware
└── utils/
    ├── __init__.py
    ├── parsers.py      # Command argument parsers
    └── formatters.py   # Message formatters
```

## Установка

```bash
# Клонировать py_accountant
git clone https://github.com/akm77/py_accountant.git
cd py_accountant

# Установить зависимости
poetry add aiogram

# Настроить переменные окружения
cp examples/telegram_bot/.env.example .env
# Отредактировать .env

# Запустить миграции
poetry run alembic upgrade head

# Запустить бота
PYTHONPATH=src poetry run python examples/telegram_bot/main.py
```

## Команды бота

### Управление валютами
- `/currencies` - Список всех валют
- `/create_currency <CODE> [rate]` - Создать валюту
- `/set_base <CODE>` - Установить базовую валюту

### Управление счетами
- `/accounts` - Список всех счетов пользователя
- `/balance [account]` - Баланс счёта

### Транзакции
- `/deposit <amount> <currency> [memo]` - Записать доход
- `/expense <amount> <currency> <category> [memo]` - Записать расход
- `/history [account] [days]` - История транзакций

### Примеры

```
/create_currency USD
/set_base USD
/create_currency EUR 1.12

/deposit 1000 USD January salary
/expense 50 USD Food Lunch at cafe
/balance
/history 7
```

## Документация

Полное руководство по интеграции: [docs/INTEGRATION_GUIDE_AIOGRAM.md](../../docs/INTEGRATION_GUIDE_AIOGRAM.md)

## Лицензия

MIT

