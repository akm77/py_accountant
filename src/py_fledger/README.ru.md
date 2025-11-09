# py_fledger (руководство на русском)

Мультивалютный модуль бухгалтерского учёта по принципу двойной записи на Python + SQLAlchemy 2.0.
Основан на идеях оригинального проекта на NodeJS/Sequelize `fledger`, адаптирован под питоновский стек и стиль.

## Цели
- План счетов (иерархическая структура, дерево субсчетов)
- Журнальные проводки из сбалансированных транзакций (дебет = кредит в базовой валюте)
- Мультивалютность за счёт хранения курса (делителя) в строках транзакции
- Кэширование балансов по счётам для ускорения агрегированных запросов
- Простое прикладное API поверх SQLAlchemy, минимум ручной ORM-рутины

## Установка
Пакет включён в монорепозиторий (см. `pyproject.toml`). Требования:
- Python 3.13+
- SQLAlchemy 2.0+
- Драйвер СУБД (например, `psycopg` для PostgreSQL; для SQLite драйвер встроен)

Пример установки в отдельном проекте:
```bash
poetry add sqlalchemy psycopg
```

## Быстрый старт
```python
from py_fledger import book

# Подключение к PostgreSQL (создайте БД заранее)
bk = book("postgresql+psycopg://user:pass@localhost:5432/fledger_db")

# Инициализация схемы (создаёт таблицы)
bk.init()

# Создаём базовую валюту (первая созданная — базовая; её курс всегда 1.0)
bk.create_currency("USD")
# Добавляем иностранную валюту
bk.create_currency("RUB")

# Создаём счета
bk.create_account("Assets")                # валюта по умолчанию USD
bk.create_account("Assets:cash")
bk.create_account("Assets:bank:AlfaBank", "RUB")
bk.create_account("UserBalances")
bk.create_account("UserBalances:1")

# Проводка (журнальная запись)
(
    bk.entry("Пополнение пользователя 1")
      .debit("Assets:cash", 10000, {"type": "userTopUp"})
      .credit("UserBalances:1", 10000, {"type": "userTopUp"})
      .commit()
)

# Проводка с иностранной валютой (курс — делитель)
(
    bk.entry("Пополнение пользователя 1 (RUB)")
      .debit("Assets:bank:AlfaBank", 600300, {"type": "userTopUp"}, 60.03)
      .credit("UserBalances:1", 10000, {"type": "userTopUp"})
      .commit()
)

# Баланс агрегированный по счёту и всем его потомкам
print(bk.balance("Assets"))  # строка (значение в базовой валюте)

# Журнал (история транзакций)
txs = bk.ledger("Assets", {"type": "userTopUp"}, {"order": "desc", "limit": 50})
for tx in txs:
    print(tx.id, tx.account_name, tx.amount, tx.credit)

# Торговый баланс — изменение позиции по валютам
print(bk.trading_balance())

bk.close()
```

## Концепции
### Счета и субсчета
Счета образуют дерево. Полное имя строится через `:` (например, `Assets:bank:AlfaBank`). Запрос баланса или журнала по родительскому счёту включает все дочерние.

### Валюты
Первая созданная валюта становится базовой. Её курс трактуется как `1.0`. Для иностранной валюты в строке транзакции указывается курс (делитель), которым делится сумма для приведения к базе.

### Журнал / Проводка
`Entry` — атомарная сбалансированная запись: набор дебетов и кредитов. Баланс проверяется в базе (с учётом делителей). Несбалансированная запись вызывает исключение.

### Транзакция
Всегда относится к одному счёту. Поля: `amount (BIGINT)`, `credit (bool)`, `memo`, `meta (JSON)`, `exchangeRate`.

### Кэш баланса
Таблица `balances` хранит накопленные промежуточные значения по счёту, чтобы ускорять расчёт: добираются только новые транзакции вместо полного пересчёта.

### Торговый баланс (Trading Balance)
Метод `trading_balance()` считает изменение позиции по каждой валюте и агрегирует её в базовой. Для больших объёмов используйте интервал по времени — сплошной расчёт может быть дорогим.

## Прикладной интерфейс (API)
### `Book(url: str)`
Создаёт контекст «книги».

Методы:
- `init()` — создаёт схему БД.
- `drop()` — удаляет схему (осторожно!).
- `close()` — освобождает ресурсы (dispose engine).
- `create_currency(code: str)` — добавляет валюту.
- `check_currency(code: str) -> dict | None` — проверяет наличие валюты.
- `create_account(name: str, currency: str | None)` — создаёт счёт (родители должны существовать).
- `check_account(name: str) -> SafeAccount | None` — получить информацию о счёте.
- `get_accounts(parent: str | None) -> list[SafeAccount]` — дерево счетов.
- `balance(account: str) -> str` — суммарный баланс (строка; для совместимости и безопасности больших чисел).
- `ledger(account: str, meta: dict | None, options: dict | None) -> list[RichTransaction]`
  - `options`: `startDate`, `endDate`, `offset`, `limit`, `order` (`'asc'|'desc'`).
- `trading_balance(options: dict | None) -> {"currency": {code: str}, "base": str}` — торговый баланс.
- `entry(memo: str) -> Entry` — начать формирование проводки.

### `Entry`
Цепочный интерфейс:
- `debit(account, amount, meta=None, exchange_rate=None)`
- `credit(account, amount, meta=None, exchange_rate=None)`
- `commit()` — проверка баланса, запись `JournalEntry` и связанных `Transaction`.

Правила:
- `amount` — целое число > 0 (хранится как BIGINT).
- Для базовой валюты `exchange_rate` игнорируется и принудительно равен 1.0.
- Для иностранной валюты, если курс не указан, берётся последний сохранённый курс из таблицы `currencies`; иначе — ошибка.

### `RichTransaction`
Структура:
```
{
  id: int,
  account_name: str,
  account_path: list[str],
  amount: int,            # хранится целым
  credit: bool,
  currency: str,
  exchange_rate: float,
  memo: str | None,
  meta: dict | None,
  created_at: datetime
}
```

## Валидация и ошибки
Доменные проверки выбрасывают `FError` (унаследован от `Exception`). Рекомендуется обрабатывать бизнес-ошибки отдельно от инфраструктурных.

## Отличия от оригинального JS-варианта
- SQLAlchemy 2.0 Declarative + типы `Mapped`
- Отказ от `bignumber.js`: суммы — целые; для итогов используются строки (совместимость/безопасность)
- Временные метки timezone-aware (`datetime.now(timezone.utc)`)
- Поддерживается режим in-memory SQLite для тестов (StaticPool + `check_same_thread=False`)

## Производительность
- Кэширование балансов уменьшает число сканируемых транзакций.
- Для PostgreSQL рекомендуются индексы:
  ```sql
  CREATE INDEX ON transactions (accountId, createdAt);
  CREATE INDEX ON balances (accountId);
  CREATE INDEX ON accounts (fullName);
  ```

## Ограничения / TODO
- Нет сторнирования / «void» транзакций (используйте обратную проводку)
- Нет фильтрации баланса по полю `meta`
- Нет переноса счёта к другому родителю
- Нет принудительного пересчёта кэша балансов
- Нет исторических (backdated) транзакций за прошлые даты

## Тесты
В репозитории есть модульные тесты на основе SQLite in-memory (`tests/unit/py_fledger`). Запуск:
```bash
pytest -q
```

## Лицензия
Следуйте лицензии основного проекта либо добавьте свою (пока не указана).

## Вклад
Pull Request'ы (PR) с улучшениями приветствуются: документация, оптимизация запросов, дополнительные методы учёта.

## Дополнительные материалы
- Подробно о торговом балансе: `TRADING_BALANCE.md`
- Диаграммы алгоритма trading_balance: `TRADING_BALANCE_DIAGRAMS.md`
- Mermaid-диаграмма trading_balance: `TRADING_BALANCE.mmd`
- Repository Planning Graph (архитектурный план): `rpg.yaml`

