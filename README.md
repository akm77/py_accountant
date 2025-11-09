## Вклад
PR с улучшениями приветствуются: документация, оптимизация, новые тесты.
# py-accountant

Чистая архитектура для бухгалтерского ядра на Python 3.13+ и SQLAlchemy 2.x. Монорепозиторий содержит слои Domain/Application/Infrastructure/Presentation и совместимый пакет py_fledger (двойная запись).

- Язык: Python 3.13+
- ORM: SQLAlchemy 2.x
- Тесты: Pytest
- Форматирование/линт: Ruff
- Управление зависимостями: Poetry

## Установка и запуск

1) Установите Poetry (если не установлен):

```bash
curl -sSL https://install.python-poetry.org | python3 -
```

Убедитесь, что `~/.local/bin` в вашем PATH.

2) Установите зависимости и создайте виртуальную среду:

```bash
poetry install --with dev
```

3) (Опционально) активируйте среду:

```bash
poetry shell
```

4) Запустите тесты:

```bash
poetry run pytest -q
```

5) Линт и форматирование:

```bash
poetry run ruff check .
poetry run ruff format .
```

6) Установите pre-commit хуки:

```bash
poetry run pre-commit install
```

### Использование как пакет
Пакет публикуется как `py-accountant`, импортируется как `py_accountant` (src/ layout).

```python
import py_accountant
print(py_accountant.get_version())
```

## Архитектура (обзор)
- domain/ — value-объекты, доменные сервисы (балансы, политика курсов).
- application/ — DTO и use case'ы (создание валют/счётов, постинг транзакций, отчёты/балансы, курсы).
- infrastructure/ — адаптеры (SQLAlchemy репозитории и UoW, in-memory реализации, Alembic миграции, настройки и логирование).
- presentation/ — CLI (и будущий API).

Слои взаимодействуют через порты (протоколы) и DTO, что упрощает замену инфраструктуры без изменения бизнес-логики.

## Быстрый старт (In-Memory)
Минимальный пример постинга транзакции и получения баланса в памяти:

```python
from datetime import UTC, datetime
from decimal import Decimal

from application.dto.models import EntryLineDTO
from application.use_cases.ledger import CreateAccount, CreateCurrency, GetBalance, PostTransaction
from infrastructure.persistence.inmemory.uow import InMemoryUnitOfWork
from infrastructure.persistence.inmemory.clock import FixedClock

uow = InMemoryUnitOfWork()
clock = FixedClock(datetime.now(UTC))

# Валюта и счета
CreateCurrency(uow)("USD")
CreateAccount(uow)("Assets:Cash", "USD")
CreateAccount(uow)("Income:Sales", "USD")

# Постим сбалансированную транзакцию
post = PostTransaction(uow, clock)
post([
    EntryLineDTO(side="DEBIT", account_full_name="Assets:Cash", amount=Decimal("100"), currency_code="USD"),
    EntryLineDTO(side="CREDIT", account_full_name="Income:Sales", amount=Decimal("100"), currency_code="USD"),
])

# Баланс
get_balance = GetBalance(uow, clock)
print(get_balance("Assets:Cash"))  # 100
```

## Подключение SQL-кэша балансов (DI)
Инкрементальный кэш балансов ускоряет повторные запросы. Подключается через `SqlAccountBalanceService`:

```python
from datetime import UTC, datetime
from decimal import Decimal

from application.dto.models import EntryLineDTO
from application.use_cases.ledger import CreateAccount, CreateCurrency, GetBalance, PostTransaction
from domain.services.account_balance_service import SqlAccountBalanceService
from infrastructure.persistence.inmemory.clock import FixedClock
from infrastructure.persistence.sqlalchemy.uow import SqlAlchemyUnitOfWork

# SQLAlchemy UoW (SQLite in-memory для демо)
uow = SqlAlchemyUnitOfWork(url="sqlite+pysqlite:///:memory:")
clock = FixedClock(datetime.now(UTC))

# Инициализация
CreateCurrency(uow)("USD", exchange_rate=Decimal("1"))
CreateAccount(uow)("Assets:Cash", "USD")
CreateAccount(uow)("Income:Sales", "USD")

# Сервис балансов
balance_service = SqlAccountBalanceService(transactions=uow.transactions, balances=uow.balances)

# Постинг
post = PostTransaction(uow, clock, balance_service=balance_service)
post([
    EntryLineDTO(side="DEBIT", account_full_name="Assets:Cash", amount=Decimal("50"), currency_code="USD"),
    EntryLineDTO(side="CREDIT", account_full_name="Income:Sales", amount=Decimal("50"), currency_code="USD"),
])

# Чтение баланса (кэш/инкремент). Поддерживается recompute=True
get_balance = GetBalance(uow, clock, balance_service=balance_service)
print(get_balance("Assets:Cash"))
print(get_balance("Assets:Cash", recompute=True))
```

Примечания:
- Без `balance_service` `GetBalance` выполнит прямую агрегацию через `transactions.account_balance`.
- `PostTransaction` вызывает `process_transaction` сервиса, если он передан.

## Торговый баланс (Detailed)
Расширенный торговый баланс с явной конверсией по базовой валюте:
- Всегда заполняет `converted_debit`, `converted_credit`, `converted_balance`.
- Поля `rate_used` и `rate_fallback` показывают источник курса и факт fallback (rate=1).
- Требует явной `base_currency`, `base_total` = сумма `converted_balance`.

```python
from datetime import UTC, datetime
from decimal import Decimal

from application.dto.models import EntryLineDTO
from application.use_cases.ledger import CreateAccount, CreateCurrency, PostTransaction, GetTradingBalanceDetailed
from infrastructure.persistence.sqlalchemy.uow import SqlAlchemyUnitOfWork
from infrastructure.persistence.inmemory.clock import FixedClock

uow = SqlAlchemyUnitOfWork(url="sqlite+pysqlite:///:memory:")
clock = FixedClock(datetime.now(UTC))

CreateCurrency(uow)("USD", exchange_rate=Decimal("1"))
CreateAccount(uow)("Assets:Cash", "USD")
CreateAccount(uow)("Income:Sales", "USD")

PostTransaction(uow, clock)([
    EntryLineDTO(side="DEBIT", account_full_name="Assets:Cash", amount=Decimal("10"), currency_code="USD"),
    EntryLineDTO(side="CREDIT", account_full_name="Income:Sales", amount=Decimal("10"), currency_code="USD"),
])

balance = GetTradingBalanceDetailed(uow, clock)("USD")
for line in balance.lines:
    print(line.currency_code, line.converted_balance, line.rate_used, line.rate_fallback)
```

## Базовая валюта и курсы (NS4)
Поддерживается явная базовая валюта (`CurrencyDTO.is_base`). В системе должна быть ровно одна базовая валюта:
- `CurrencyRepository.set_base(code)` обеспечивает синглтон (предыдущая база снимается).
- Для базовой `exchange_rate=None` (внутренний курс = 1).
- `GetTradingBalance` умеет инферить базовую валюту, если аргумент не передан, а база уже задана.
- `GetTradingBalanceDetailed` требует явный `base_currency`.

Обновление курсов пакетно через `UpdateExchangeRates` с политикой (last_write/weighted_average):

```python
from datetime import UTC, datetime
from decimal import Decimal

from application.dto.models import RateUpdateInput
from application.use_cases.exchange_rates import UpdateExchangeRates
from application.use_cases.ledger import CreateCurrency
from domain import ExchangeRatePolicy
from infrastructure.persistence.sqlalchemy.uow import SqlAlchemyUnitOfWork
from infrastructure.persistence.inmemory.clock import FixedClock

uow = SqlAlchemyUnitOfWork(url="sqlite+pysqlite:///:memory:")
clock = FixedClock(datetime.now(UTC))

CreateCurrency(uow)("USD")
CreateCurrency(uow)("EUR")
updates = [RateUpdateInput(code="EUR", rate=Decimal("1.2345678900"))]
UpdateExchangeRates(uow, policy=ExchangeRatePolicy(mode="last_write"))(updates, set_base="USD")
```

Правила валидации:
- Коды нормализуются через VO `CurrencyCode` (верхний регистр, ASCII alnum + `_`, ограничение длины).
- Курсы > 0; неверные значения → `DomainError`.
- Политики: `last_write`, `weighted_average`.

Поведение `set_base` (важно): базовая валюта должна существовать заранее. Если вызвать `set_base` с неизвестным кодом — будет `DomainError`. Делайте явный `CreateCurrency` → затем `set_base`.

## Политика округления (NS11)
Единая квантовка Decimal:
- `money_quantize` (по умолчанию до 2 знаков, `ROUND_HALF_EVEN`) для денежных значений.
- `rate_quantize` (по умолчанию до 10 знаков) для курсов.

Настройка через переменные окружения:
```bash
export MONEY_SCALE=2
export RATE_SCALE=10
export ROUNDING=ROUND_HALF_EVEN
```

## Миграции Alembic
Первая ревизия (`0001_initial`) создаёт таблицы: currencies, accounts, journals, transaction_lines, balances.
Вторая ревизия (`0002_add_is_base_currency`) добавляет колонку `currencies.is_base`.

Запуск/откат:
```bash
poetry run alembic upgrade head
poetry run alembic downgrade -1
```

Генерация новой ревизии:
```bash
poetry run alembic revision --autogenerate -m "add new table"
```

Убедитесь, что `DATABASE_URL` задан в окружении для таргетной БД.

## RecalculateAccountBalance (NS5)
Use case для принудительного полного пересчёта баланса счёта до момента времени `as_of`.

Зачем:
- Обновить кэш после подозрения на рассинхронизацию.
- Получить исторический баланс в прошлом (`as_of` раньше кэша).
- Единая точка для освежения кэша (SQL/in-memory).

Контракт (подпись):
```python
# RecalculateAccountBalance(uow, clock, balance_service=None)(account_full_name, as_of=None, force=True) -> Decimal
```

Поведение:
- При наличии баланс-сервиса (`SqlAccountBalanceService` или `InMemoryAccountBalanceService`) используется `get_balance(..., recompute=True)` с обновлением кэша.
- Без сервиса — прямая агрегация через `uow.transactions.account_balance(account_full_name, as_of)` (без кэширования).

Пример (SQL):
```python
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from application.dto.models import EntryLineDTO
from application.use_cases.ledger import CreateCurrency, CreateAccount, PostTransaction, GetBalance
from application.use_cases.recalculate import RecalculateAccountBalance
from domain.services.account_balance_service import SqlAccountBalanceService
from infrastructure.persistence.sqlalchemy.uow import SqlAlchemyUnitOfWork
from infrastructure.persistence.inmemory.clock import FixedClock

uow = SqlAlchemyUnitOfWork(url="sqlite+pysqlite:///:memory:")
clock = FixedClock(datetime.now(UTC))

CreateCurrency(uow)("USD")
CreateAccount(uow)("Assets:Cash", "USD")
CreateAccount(uow)("Income:Sales", "USD")

post = PostTransaction(uow, clock)
post([
    EntryLineDTO(side="DEBIT", account_full_name="Assets:Cash", amount=Decimal("50"), currency_code="USD"),
    EntryLineDTO(side="CREDIT", account_full_name="Income:Sales", amount=Decimal("50"), currency_code="USD"),
])
post([
    EntryLineDTO(side="DEBIT", account_full_name="Assets:Cash", amount=Decimal("25"), currency_code="USD"),
    EntryLineDTO(side="CREDIT", account_full_name="Income:Sales", amount=Decimal("25"), currency_code="USD"),
])

svc = SqlAccountBalanceService(transactions=uow.transactions, balances=uow.balances)
get_balance = GetBalance(uow, clock, balance_service=svc)
recalc = RecalculateAccountBalance(uow, clock, balance_service=svc)

current = get_balance("Assets:Cash")
past = clock.now() - timedelta(seconds=5)
historical = recalc("Assets:Cash", as_of=past)  # полный пересчёт до past
latest = recalc("Assets:Cash")                  # принудительный пересчёт на сейчас
print(current, historical, latest)
```

## CLI (программный доступ)
Минимальный пример вызова CLI из Python (использует `argparse`):

```python
from presentation.cli.main import main

# добавить валюту
main(["currency:add", "USD"])
# назначить базовую валюту (валюта должна существовать)
main(["currency:set-base", "USD"])
# обновить курс
main(["fx:update", "EUR", "1.10"])
# постинг простой транзакции через --line (см. раздел ниже)
main(["tx:post", "--line", "DEBIT:Assets:Cash:100:USD", "--line", "CREDIT:Income:Sales:100:USD"])
# получить баланс
main(["balance:get", "Assets:Cash"])
# принудительный пересчёт
main(["balance:recalc", "Assets:Cash"])
```

## CLI Usage (через Poetry / python -m)
Запуск команд из репозитория:

```bash
poetry run python -m presentation.cli.main currency:add USD
poetry run python -m presentation.cli.main currency:add EUR
poetry run python -m presentation.cli.main currency:set-base USD
poetry run python -m presentation.cli.main fx:update EUR 1.2345
poetry run python -m presentation.cli.main account:add Assets:Cash USD
poetry run python -m presentation.cli.main account:add Income:Sales USD
poetry run python -m presentation.cli.main tx:post --line DEBIT:Assets:Cash:100:USD --line CREDIT:Income:Sales:100:USD --memo "Initial sale"
poetry run python -m presentation.cli.main balance:get Assets:Cash --json
poetry run python -m presentation.cli.main trading:detailed --base USD --json
poetry run python -m presentation.cli.main ledger:list Assets:Cash --limit 10 --json
```

Глобальные флаги (могут идти до или после команды):
- `--db-url` URL базы (если не указан — in-memory адаптеры)
- `--log-level` уровень логирования (по умолчанию INFO)
- `--json-logs` включить структурированные JSON-логи
- `--policy` политика курсов (`last_write` | `weighted_average`), влияет на `fx:update` и обработку `exchange_rate` в `tx:post`
- `--json` вывод в JSON вместо human

Команды:
- `currency:add CODE` — создать валюту (idempotent для повторного вызова)
- `currency:list` — список валют
- `currency:set-base CODE` — назначить существующую валюту базовой (явно)
- `fx:update CODE RATE` — обновить курс (ошибка, если CODE неизвестен или RATE <= 0)
- `fx:batch PATH` — пакетное обновление из JSON-массива объектов `{code, rate}`
- `account:add FULL_NAME CURRENCY` — создать счёт в валюте (idempotent: при наличии вернёт 0)
- `tx:post --line side:account:amount:currency[:rate]` — добавить сбалансированную транзакцию (две и более линии). Имя счёта может содержать двоеточия — парсинг идёт справа-налево.
- `balance:get ACCOUNT [--as-of ISO8601]` — получить баланс (кэш/агрегация)
- `balance:recalc ACCOUNT [--as-of ISO8601]` — принудительный пересчёт
- `trading:balance [--base CODE] [--as-of ISO8601]` — агрегированный торговый баланс; base инферится, если задана в repo
- `trading:detailed --base CODE [--as-of ISO8601]` — детальный торговый баланс (обязателен base)
- `ledger:list ACCOUNT [--start ISO8601 --end ISO8601 --offset N --limit N --order ASC|DESC --meta k=v]` — список транзакций

Вывод:
- По умолчанию human-readable строки (Currency/Account/Transaction/TradingBalance).
- С `--json` происходит сериализация DTO: `Decimal` -> `str`, `datetime` -> ISO8601.

Коды выхода:
- 0 — успех
- 2 — DomainError (валидация: неизвестная валюта/счёт, плохой курс/сумма, неверный формат и т.п.)
- 1 — неожиданная ошибка (ошибка инфраструктуры/кода)

Примечания по UX/валидации:
- `currency:set-base` требует, чтобы валюта была заранее создана.
- `fx:update`/`fx:batch` отвергают нулевые/отрицательные курсы.
- `tx:post` требует положительные суммы; `--line` парсится справа налево, поддерживает `:rate` в конце.
- `ledger:list` проверяет формат имени счёта и параметры пагинации/сортировки.

Производительность (smoke):
- В тестах есть сценарий постинга 1000 транзакций и выборки леджера с `limit=50`. Он служит дымовой проверкой и проходит без логических ошибок.

## Тесты
Запуск всех тестов:

```bash
poetry run pytest -q
```

Для запуска только CLI-тестов:

```bash
poetry run pytest tests/e2e/cli -q
poetry run pytest tests/unit/presentation/test_cli_errors.py -q
```

## Примечания
- SQLAlchemy на ветке 2.x (`^2.0.0`).
- Python 3.13+ (см. `pyproject.toml`).
- Для CLI в тестах in-memory состояние разделяется по тестам (используется `PYTEST_CURRENT_TEST`).

## Exchange Rate Policy (Политика обновления курсов)

Политика определяет как пересчитывается `exchange_rate` при поступлении нового наблюдаемого курса.

Доступные режимы:

1. `last_write` — последний курс просто перезаписывает предыдущий.
   Формула:
   ```text
   new_rate = observed
   ```
   Используется для максимальной простоты и мгновенного отражения последнего значения.

2. `weighted_average` — инкрементальное среднее всех наблюдаемых курсов за время жизни экземпляра политики.
   В реализации хранится счётчик наблюдений `seen_count` внутри объекта `ExchangeRatePolicy`.
   Формула шага:
   - Первый шаг (когда есть предыдущий):
     ```text
     new_rate = (prev + observed) / 2
     ```
   - Последующие шаги:
     ```text
     new_rate = (prev * count_prev + observed) / (count_prev + 1)
     ```
     где `prev` уже является средним предыдущих наблюдений, `count_prev` — их количество.

   Защиты:
   - Если `previous is None` или `previous <= 0`, используется fallback к `observed` и `seen_count` сбрасывается в 1.
   - Если `observed <= 0` — выбрасывается ошибка (некорректный курс).

   Назначение режима — сглаживание резких скачков курса без хранения полной истории. Историчность (аудит) отложена.

Переопределение политики:
- Глобальная политика задаётся через флаг CLI `--policy` (например при запуске `fx:update` или `tx:post`).
- Локальная политика для пакетного обновления задаётся через `fx:batch --policy ...` и имеет приоритет над глобальной.

Пример локального override:
```bash
poetry run python -m presentation.cli.main --policy last_write currency:add USD
poetry run python -m presentation.cli.main --policy last_write currency:add EUR
poetry run python -m presentation.cli.main --policy last_write fx:update EUR 1.0000
# Применим пакет с локальной weighted_average
poetry run python -m presentation.cli.main --policy last_write fx:batch rates.json --policy weighted_average
```
`rates.json`:
```json
[
  {"code": "EUR", "rate": 2.0}
]
```
После выполнения `fx:batch` новый курс EUR будет усреднён: (1.0 + 2.0)/2 = 1.5.

Команда диагностики курсов:
- `diagnostics:rates` — выводит список валют с текущим `rate`, признаком `is_base` и активной глобальной политикой (если задана). Формат human или `--json`.

Квантование:
- Курс нормализуется через `rate_quantize` (см. раздел округления).
- Величины торгового баланса при необходимости нормализуются флагом `--normalize` для `trading:detailed`.

Границы и ограничения:
- Не поддерживается пер-валютный счётчик наблюдений (будущая итерация).
- Историческая выборка курсов (audit trail) отложена.

Рекомендации использования:
- Используйте `last_write` при частых обновлениях из доверенного источника.
- Используйте `weighted_average` при шумных котировках для сглаживания.

