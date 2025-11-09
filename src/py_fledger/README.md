# py_fledger

Мультивалютный модуль двойной записи (double-entry bookkeeping) на Python + SQLAlchemy 2.0.
Основан на идеях оригинального NodeJS/Sequelize проекта `fledger` и портирован в питоновский стиль.

## Цели
- План счетов (иерархия / дерево субсчетов)
- Журнальные проводки из сбалансированных транзакций (дебет = кредит в базовой валюте)
- Мультивалютность через хранение курсов (делитель) в транзакциях
- Кэширование изолированных балансов для ускорения агрегированных запросов
- Простое API поверх SQLAlchemy, минимизация ручной ORM-рутины

## Установка
Добавьте пакет в ваш проект (уже включён в `pyproject.toml`). Требуемые зависимости:
- Python 3.13+
- SQLAlchemy 2.0+
- Драйвер базы (например `psycopg` для PostgreSQL или встроенный SQLite)

Пример установки в отдельном проекте:
```bash
poetry add sqlalchemy psycopg
```

## Быстрый старт
```python
from py_fledger import book

# Подключение к Postgres (создайте БД заранее)
bk = book("postgresql+psycopg://user:pass@localhost:5432/fledger_db")

# Инициализация схемы (создаёт таблицы)
bk.init()

# Создаём базовую валюту (первая = база, её курс всегда 1.0)
bk.create_currency("USD")
# Добавляем иностранную валюту
bk.create_currency("RUB")

# Создаём счета
bk.create_account("Assets")                # базовая валюта USD
bk.create_account("Assets:cash")
bk.create_account("Assets:bank:AlfaBank", "RUB")
bk.create_account("UserBalances")
bk.create_account("UserBalances:1")

# Проводка (журнальная запись)
(
    bk.entry("User 1 top up")
      .debit("Assets:cash", 10000, {"type": "userTopUp"})
      .credit("UserBalances:1", 10000, {"type": "userTopUp"})
      .commit()
)

# Проводка с иностранной валютой (курс — делитель)
(
    bk.entry("User 1 RUB top up")
      .debit("Assets:bank:AlfaBank", 600300, {"type": "userTopUp"}, 60.03)
      .credit("UserBalances:1", 10000, {"type": "userTopUp"})
      .commit()
)

# Баланс агрегированный по счёту и всем его потомкам
print(bk.balance("Assets"))  # строка вида '...' (значение в базовой валюте)

# История транзакций
txs = bk.ledger("Assets", {"type": "userTopUp"}, {"order": "desc", "limit": 50})
for tx in txs:
    print(tx.id, tx.account_name, tx.amount, tx.credit)

# Торговый (trading) баланс – изменение позиции по валютам
print(bk.trading_balance())

bk.close()
```

## Концепции
### Счета и субсчета
Счета образуют дерево. Полное имя формируется через `:` (например `Assets:bank:AlfaBank`). При запросе баланса или истории на родительском счёте включаются все дочерние.

### Валюты
Первая созданная валюта — базовая. Её курс всегда трактуется как `1.0`. Для иностранной валюты в транзакции указывается курс (делитель), которым делят сумму для приведения к базе.

### Журнал / Проводка
`Entry` — атомарная сбалансированная запись: набор дебетов и кредитов. Баланс проверяется в пересчитанной базе (с учётом делителей). Несбалансированная запись вызывает исключение.

### Транзакция
Всегда относится к одному счёту. Поля: `amount (BIGINT)`, `credit (bool)`, `memo`, `meta (JSON)`, `exchangeRate`.

### Кэш баланса
Таблица `balances` хранит накопленные промежуточные значения для конкретного счёта, чтобы быстрым SQL добирать только новые транзакции вместо полного пересчёта.

### Торговый баланс (Trading Balance)
Метод `trading_balance()` считает изменение позиции по каждой валюте и агрегирует её в базовой. Используйте периодические интервалные запросы (иначе при больших объёмах может быть дорого).

## API
### Book(url: str)
Создаёт контекст книги.

Методы:
- `init()` — создаёт схему.
- `drop()` — удаляет схему (осторожно!).
- `close()` — освобождает ресурсы (dispose engine).
- `create_currency(code: str)` — добавляет валюту.
- `check_currency(code: str) -> dict | None` — проверяет наличие.
- `create_account(name: str, currency: str | None)` — создаёт счёт (родители должны существовать).
- `check_account(name: str) -> SafeAccount | None`.
- `get_accounts(parent: str | None) -> list[SafeAccount]` — дерево.
- `balance(account: str) -> str` — суммарный баланс (строка). Возвращается строка для совместимости и безопасности больших чисел.
- `ledger(account: str, meta: dict | None, options: dict | None) -> list[RichTransaction]`
  - `options`: `startDate`, `endDate`, `offset`, `limit`, `order` ('asc'|'desc').
- `trading_balance(options: dict | None) -> {"currency": {code: str}, "base": str}`.
- `entry(memo: str) -> Entry` — создать объект проводки.

### Entry
Цепочный интерфейс:
- `debit(account, amount, meta=None, exchange_rate=None)`
- `credit(account, amount, meta=None, exchange_rate=None)`
- `commit()` — проверяет баланс, пишет `JournalEntry` и связанные `Transaction`.

Правила:
- `amount` должен быть целым > 0 (хранится как BIGINT).
- Для базовой валюты `exchange_rate` игнорируется и принудительно = 1.0.
- Для иностранной валюты, если курс не указан — берётся последний сохранённый курс из таблицы `currencies`, иначе ошибка.

### RichTransaction
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
Все проверки выбрасывают `FError` (унаследован от `Exception`). Отлавливайте бизнес-ошибки отдельно от инфраструктурных.

## Отличия от оригинального JS варианта
- Используется SQLAlchemy 2.0 Declarative + `Mapped` типы
- Отказ от `bignumber.js`: целочисленные суммы, строки для итогов (совместимость / отсутствие переполнения)
- Таймстемпы timezone-aware (`datetime.now(timezone.utc)`)
- Возможен in-memory SQLite режим для тестов (StaticPool + `check_same_thread=False`)

## Производительность
- Кэширование балансов уменьшает количество сканируемых транзакций.
- Добавьте индексы при использовании PostgreSQL:
  ```sql
  CREATE INDEX ON transactions (accountId, createdAt);
  CREATE INDEX ON balances (accountId);
  CREATE INDEX ON accounts (fullName);
  ```

## Ограничения / TODO
- Нет механизма сторнирования / void транзакций (используйте обратную проводку)
- Нет фильтрации баланса по `meta`
- Нет переноса счёта к другому родителю
- Нет пересчёта кеша балансов принудительно
- Нет исторических (backdated) транзакций за прошлые даты

## Тесты
В репозитории есть модульные тесты на основе SQLite in-memory (`tests/unit/py_fledger`). Запустите:
```bash
pytest -q
```

## Лицензия
Следуйте лицензии основного проекта или добавьте свою (пока не указана).

## Вклад
PR с улучшениями приветствуются: документация, оптимизация запросов, дополнительные методы учёта.

## Дополнительные материалы
- Подробно о торговом балансе: см. файл `TRADING_BALANCE.md`
- Диаграммы алгоритма trading_balance: файл `TRADING_BALANCE_DIAGRAMS.md`
- Mermaid диаграмма trading_balance: `TRADING_BALANCE.mmd`
- Repository Planning Graph (архитектурный план): файл `rpg.yaml`
