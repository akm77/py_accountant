# Trading Windows (Async)

Коротко: отчеты по операциям за окно времени. Две команды:
- trading raw — агрегирует по валютам без конверсии.
- trading detailed — агрегирует и конвертирует в базовую валюту.

CLI — async-only: команды вызывают асинхронные use case'ы, без каких-либо sync-обёрток.

## Назначение
- Быстро посчитать обороты и сальдо по валютам за заданный период.
- Выгрузить результат в JSON для автоматической обработки.

## Тайм-окно
- Параметры: --start, --end — строки в ISO8601.
- Naive дата/время (без таймзоны) → трактуем как UTC.
- Невалидная строка даты/времени → ошибка «Invalid datetime».
- Если --start не указан, берём эпоху (0) с той же таймзоной, что и «сейчас».
- Если --end не указан, берём текущее время (UTC).
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
- Флаг: `--meta k=v` (можно указывать несколько раз).
- Дубликаты ключей: «последний побеждает».
- Ошибки формата: нет «=» → «Invalid meta item; expected k=v»; пустой ключ/значение → «Invalid meta item; empty key or value».

## Команда: trading raw
Агрегация по валютам без конверсии.

Параметры:
- --start, --end — ISO8601; naive → UTC.
- --meta k=v — фильтр по метаданным (строгое совпадение всех пар).
- --json — вывод JSON.

Формат JSON (список объектов):
- currency_code, debit, credit, net — все значения как строки; деньги с 2 знаками.

Примеры через Python API:

```python
from py_accountant.application.use_cases_async.trading_balance import (
    AsyncGetTradingBalanceRaw
)
from datetime import datetime, UTC

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
    
    for line in result:
        print(f"{line.currency_code}: debit={line.debit}, credit={line.credit}, net={line.net}")
```

## Команда: trading detailed
Агрегация и конверсия в базовую валюту. Требуется валидная base.

Откуда берётся base:
- Явно через `--base CODE` (пустая строка → «Empty base currency code»; неизвестный код → «Base currency not found: 'CODE'»).
- Или из справочника валют (если отмечена одна базовая). Если не удаётся определить → «Base currency is not defined».

Поведение detailed:
- Для строки в базовой валюте: `used_rate = 1.000000` (после квантизации в 6 знаков).
- Для небазовой валюты требуется `rate_to_base > 0`; иначе ошибка:
  - Нет курса → «Missing rate_to_base for currency: CODE».
  - Неположительный курс → «Non-positive rate_to_base for currency: CODE».
- Неизвестная валюта из проводок → «Unknown currency in entry: 'CODE'».

Параметры:
- --start, --end — ISO8601; naive → UTC.
- --meta k=v — фильтр по метаданным.
- --base CODE — код базовой валюты (тримминг, upper-case).
- --json — вывод JSON.

Формат JSON (список объектов):
- currency_code, base_currency_code,
- debit, credit, net,
- used_rate,
- debit_base, credit_base, net_base.

Все значения — строки. Деньги с 2 знаками; used_rate с 6 знаками.

Примеры (через SDK):
- Отчёт с явной базовой валютой:
  ```python
  from datetime import datetime
  from application.use_cases_async.trading_balance import AsyncGetTradingBalanceDetailed
  async with app.uow_factory() as uow:
      detailed = await AsyncGetTradingBalanceDetailed(uow, app.clock)(
          base_currency="USD",
          start=datetime(2025, 11, 10, 10, 0, 0),
          end=datetime(2025, 11, 10, 12, 0, 0)
      )
  ```

## Ошибки и валидация (типичные сообщения)
- Дата/время:
  - Неверный формат → «Invalid datetime».
  - start > end → «start > end».
- Meta:
  - Нет «=» → «Invalid meta item; expected k=v».
  - Пустой ключ/значение → «Invalid meta item; empty key or value».
- Base (только detailed):
  - Пустой `--base` → «Empty base currency code».
  - База не определена (нет --base и нет базовой в справочнике) → «Base currency is not defined».
  - Неизвестная база по коду → «Base currency not found: 'CODE'».
- Валюты в проводках:
  - Неизвестная валюта → «Unknown currency in entry: 'CODE'».
- Курс:
  - Нет курса для небазовой → «Missing rate_to_base for currency: CODE».
  - Курс ≤ 0 → «Non-positive rate_to_base for currency: CODE».

## Примеры JSON
Raw:
```json
[
  {"currency_code":"USD","debit":"100.00","credit":"40.00","net":"60.00"},
  {"currency_code":"EUR","debit":"50.00","credit":"10.00","net":"40.00"}
]
```

Detailed:
```json
[
  {"currency_code":"USD","base_currency_code":"USD","debit":"100.00","credit":"40.00","net":"60.00","used_rate":"1.000000","debit_base":"100.00","credit_base":"40.00","net_base":"60.00"},
  {"currency_code":"EUR","base_currency_code":"USD","debit":"50.00","credit":"10.00","net":"40.00","used_rate":"1.123400","debit_base":"56.17","credit_base":"11.23","net_base":"44.94"}
]
```

Примечание: JSON печатается только если указан флаг `--json`.

## Ограничения и замечания
Пагинации нет. Большие выборки могут потребовать много памяти — используйте узкие окна и фильтры meta.
- Результат отсортирован по коду валюты.

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
