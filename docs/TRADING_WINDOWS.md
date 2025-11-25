# Trading Windows (Async)

Коротко: отчеты по операциям за окно времени. Два use case:
- **AsyncGetTradingBalanceRaw** — агрегирует по валютам без конверсии.
- **AsyncGetTradingBalanceDetailed** — агрегирует и конвертирует в базовую валюту.

Оба use case являются async-only и работают через AsyncUnitOfWork.

## Назначение
- Быстро посчитать обороты и сальдо по валютам за заданный период.
- Выгрузить результат в JSON для автоматической обработки.

## Тайм-окно
- Параметры: `start`, `end` — объекты `datetime`.
- Naive дата/время (без таймзоны) → трактуем как UTC.
- Невалидный datetime → ошибка «Invalid datetime».
- Если `start=None`, берём эпоху (0) с той же таймзоной, что и «сейчас».
- Если `end=None`, берём текущее время (UTC).
- Если start > end → ошибка («start > end»).
- Пустой диапазон (start == end) или нет транзакций → пустой список в ответе.

Небольшой таймлайн:
```
|----Transactions----|---------------------->
0              start            end(now)
                [  window   ]
```

## Квантизация и форматы
- Деньги (debit/credit/net/..._base): 2 знака, ROUND_HALF_EVEN.
- Курс (used_rate): 6 знаков, ROUND_HALF_EVEN.
- Decimal сериализуется в JSON как строка.
- Datetime — ISO8601 в UTC (окончание на Z или +00:00).

См. правила в `src/domain/quantize.py` и обзор в `docs/ARCHITECTURE_OVERVIEW.md`.

## Фильтры meta
- Параметр: `meta: dict[str, str] | None` — словарь для фильтрации транзакций.
- Логика: строгое совпадение всех пар ключ-значение.
- Если `meta=None` или `meta={}` — фильтр не применяется (все транзакции).

## Use Case: AsyncGetTradingBalanceRaw

Агрегация по валютам без конверсии.

**Импорт**:
```python
from py_accountant.application.use_cases_async.trading_balance import AsyncGetTradingBalanceRaw
```

**Сигнатура**:
```python
async def __call__(
    self,
    *,
    start: datetime | None = None,
    end: datetime | None = None,
    meta: dict[str, Any] | None = None,
) -> list[TradingBalanceLineSimple]
```

**Параметры**:
- `start` (datetime | None) — начало окна; если None, берётся эпоха
- `end` (datetime | None) — конец окна; если None, берётся текущее время
- `meta` (dict | None) — фильтр по метаданным транзакций

**Возвращает**: Список `TradingBalanceLineSimple` с полями:
- `currency_code: str` — код валюты
- `debit: Decimal` — сумма по дебету (2 знака)
- `credit: Decimal` — сумма по кредиту (2 знака)
- `net: Decimal` — чистая позиция (debit - credit, 2 знака)

**Примеры**:

```python
from py_accountant.application.use_cases_async.trading_balance import AsyncGetTradingBalanceRaw
from datetime import datetime, UTC

# Инициализация use case
async with uow_factory() as uow:
    use_case = AsyncGetTradingBalanceRaw(uow, clock)
    
    # Все операции до текущего момента
    result = await use_case()
    
    # Явный интервал и фильтр по meta
    result = await use_case(
        start=datetime(2025, 11, 10, 10, 0, 0, tzinfo=UTC),
        end=datetime(2025, 11, 10, 12, 0, 0, tzinfo=UTC),
        meta={"source": "exchange", "user": "alice"}
    )
    
    # Обработка результата
    for line in result:
        print(f"{line.currency_code}: debit={line.debit}, credit={line.credit}, net={line.net}")
```

**Формат для JSON** (при сериализации):
```json
[
  {"currency_code":"USD","debit":"100.00","credit":"40.00","net":"60.00"},
  {"currency_code":"EUR","debit":"50.00","credit":"10.00","net":"40.00"}
]
```

## Use Case: AsyncGetTradingBalanceDetailed

Агрегация и конверсия в базовую валюту. Требуется валидная база.

**Импорт**:
```python
from py_accountant.application.use_cases_async.trading_balance import AsyncGetTradingBalanceDetailed
```

**Сигнатура**:
```python
async def __call__(
    self,
    *,
    start: datetime | None = None,
    end: datetime | None = None,
    meta: dict[str, Any] | None = None,
    base_currency: str | None = None,
) -> list[TradingBalanceLineDetailed]
```

**Параметры**:
- `start` (datetime | None) — начало окна
- `end` (datetime | None) — конец окна
- `meta` (dict | None) — фильтр по метаданным
- `base_currency` (str | None) — код базовой валюты; если None, берётся из справочника

**Определение базовой валюты**:
- Явно через параметр `base_currency="USD"` (пустая строка → ошибка «Empty base currency code»)
- Или из справочника валют (если отмечена одна базовая)
- Если не удаётся определить → ошибка «Base currency is not defined»
- Неизвестный код → ошибка «Base currency not found: 'CODE'»

**Поведение конверсии**:
- Для строки в базовой валюте: `used_rate = 1.000000` (6 знаков)
- Для небазовой валюты требуется `rate_to_base > 0`; иначе ошибка:
  - Нет курса → «Missing rate_to_base for currency: CODE»
  - Неположительный курс → «Non-positive rate_to_base for currency: CODE»
- Неизвестная валюта из проводок → «Unknown currency in entry: 'CODE'»

**Возвращает**: Список `TradingBalanceLineDetailed` с полями:
- `currency_code: str` — код валюты
- `base_currency_code: str` — код базовой валюты
- `debit: Decimal` — сумма по дебету в валюте (2 знака)
- `credit: Decimal` — сумма по кредиту в валюте (2 знака)
- `net: Decimal` — чистая позиция в валюте (2 знака)
- `used_rate: Decimal` — использованный курс (6 знаков)
- `debit_base: Decimal` — дебет в базовой валюте (2 знака)
- `credit_base: Decimal` — кредит в базовой валюте (2 знака)
- `net_base: Decimal` — чистая позиция в базовой валюте (2 знака)

**Примеры**:

```python
from py_accountant.application.use_cases_async.trading_balance import AsyncGetTradingBalanceDetailed
from datetime import datetime, UTC

async with uow_factory() as uow:
    use_case = AsyncGetTradingBalanceDetailed(uow, clock)
    
    # С явной базовой валютой
    result = await use_case(
        base_currency="USD",
        start=datetime(2025, 11, 10, 10, 0, 0, tzinfo=UTC),
        end=datetime(2025, 11, 10, 12, 0, 0, tzinfo=UTC)
    )
    
    # Базовая из справочника
    result = await use_case(
        start=datetime(2025, 11, 10, 10, 0, 0, tzinfo=UTC),
        end=datetime(2025, 11, 10, 12, 0, 0, tzinfo=UTC),
        meta={"type": "trade"}
    )
    
    # Обработка результата
    for line in result:
        print(f"{line.currency_code} → {line.base_currency_code}")
        print(f"  Net: {line.net} (rate: {line.used_rate})")
        print(f"  Net in base: {line.net_base}")
```

**Формат для JSON** (при сериализации):
```json
[
  {
    "currency_code":"USD",
    "base_currency_code":"USD",
    "debit":"100.00",
    "credit":"40.00",
    "net":"60.00",
    "used_rate":"1.000000",
    "debit_base":"100.00",
    "credit_base":"40.00",
    "net_base":"60.00"
  },
  {
    "currency_code":"EUR",
    "base_currency_code":"USD",
    "debit":"50.00",
    "credit":"10.00",
    "net":"40.00",
    "used_rate":"1.123400",
    "debit_base":"56.17",
    "credit_base":"11.23",
    "net_base":"44.94"
  }
]
```

## Ошибки и валидация

**Типичные исключения**:

### Дата/время
- `ValueError("Invalid datetime")` — невалидный объект datetime
- `ValueError("start > end")` — начало позже конца

### Meta фильтры
- Невалидный тип meta → TypeError
- Проблемы с фильтрацией обрабатываются на уровне репозитория

### Base currency (только AsyncGetTradingBalanceDetailed)
- `ValueError("Empty base currency code")` — пустая строка в `base_currency`
- `ValueError("Base currency is not defined")` — не указана и не найдена в справочнике
- `ValueError("Base currency not found: 'CODE'")` — неизвестный код валюты

### Валюты в проводках
- `ValueError("Unknown currency in entry: 'CODE'")` — валюта не найдена в справочнике

### Курсы обмена
- `ValueError("Missing rate_to_base for currency: CODE")` — нет курса для конверсии
- `ValueError("Non-positive rate_to_base for currency: CODE")` — курс ≤ 0

## Ограничения и рекомендации

- **Пагинация отсутствует**: большие выборки могут потребовать много памяти
- **Рекомендации**: используйте узкие временные окна и фильтры `meta` для ограничения выборки
- **Сортировка**: результат отсортирован по коду валюты (currency_code)
- **Производительность**: для больших объёмов данных рассмотрите использование прямых SQL-запросов

## См. также

- [API_REFERENCE.md](API_REFERENCE.md) — полная документация use cases
- [CONFIG_REFERENCE.md](CONFIG_REFERENCE.md) — конфигурация quantization (MONEY_SCALE, RATE_SCALE)
- [ARCHITECTURE_OVERVIEW.md](ARCHITECTURE_OVERVIEW.md) — архитектура системы
- [examples/fastapi_basic](../examples/fastapi_basic/) — пример REST API с trading endpoints

## Async-only
- CLI вызывает асинхронные use cases (`application.use_cases_async.trading_balance.*`).
- Alembic использует sync-драйвер только для миграций (см. общий обзор архитектуры).

## Ссылки
- Квантизация: `src/domain/quantize.py`.
- Обзор архитектуры: `docs/ARCHITECTURE_OVERVIEW.md`.

## Мини-чеклист
- Старый формат команд с двоеточием не используется.
- Примеры CLI используют `trading raw` и `trading detailed`.
- Форматы: деньги — 2 знака; used_rate — 6 знаков; Decimal как строки; datetime — ISO8601 UTC.
- Подробно перечислены ошибки/валидация и поведение base в detailed.
