# Шпаргалка проводок (core)

Эта шпаргалка объединяет форматы строк/файлов, правила валидации, частые ошибки и идемпотентность постинга.

## Формат строки проводки

Строка: `SIDE:Account:Amount:Currency[:Rate]`

- SIDE: `DEBIT` или `CREDIT` (регистр не важен, нормализуется к верхнему).
- Account: строка с поддержкой иерархии через `:` (например, `Assets:Cash:Wallet`). В CLI‑парсере поддерживаются вложенные `:`.
- Amount: Decimal > 0 (например, `100`, `0.01`).
- Currency: только буквы, длина 3..10 (например, `USD`, `EUR`).
- Rate (опционально): Decimal > 0. Указывается для небазовых валют; иначе записи должны сходиться в базовой валюте.

Примеры:
- `DEBIT:Assets:Cash:100:USD`
- `CREDIT:Income:Sales:100:USD`
- `DEBIT:Assets:Broker:100:EUR:1.120000` (с курсом строки)

## Форматы файлов (--lines-file)

- CSV: заголовки `side,account,amount,currency[,rate]`.
  - Пустые строки пропускаются.
  - Значения нормализуются (side/currency → upper; amount/rate — строки как есть).
- JSON: массив строк в формате выше или объектов `{side,account,amount,currency[,rate]}`.

Пример JSON:
```json
[
  {"side":"DEBIT","account":"Assets:Cash","amount":"100","currency":"USD"},
  {"side":"CREDIT","account":"Income:Sales","amount":"100","currency":"USD"}
]
```

## Правила и валидация

- Суммы и курс должны быть > 0.
- Валюта — A‑Z, длина 3..10.
- SIDE — только DEBIT/CREDIT.
- Для небазовой валюты требуется положительный курс (`rate_to_base`).
- Входные naive‑даты трактуются как UTC; сериализация datetime — ISO8601 UTC (`Z`/`+00:00`).
- JSON: Decimal сериализуется строкой; порядок ключей стабилен.

Квантизация (см. `src/py_accountant/domain/quantize.py`, импорт: `from py_accountant.domain.quantize import money_quantize, rate_quantize`):
- Деньги — 2 знака, ROUND_HALF_EVEN.
- Курсы — 6 знаков, ROUND_HALF_EVEN.

## Частые ошибки и подсказки

- "Invalid line format" — проверьте шаблон `SIDE:Account:Amount:Currency[:Rate]`.
- "Invalid datetime" — используйте ISO8601 (`2025-11-13T10:00:00Z`).
- "Missing rate_to_base…" — задайте базовую валюту и/или курс для небазовой.
- "Non-positive rate…" — курс должен быть > 0.
- "Unknown currency/account" — создайте сущность до постинга.
- "Base currency is not defined" — выполните `currency set-base <CODE>`.
- "Unbalanced ledger" — дебет/кредит не сходятся в базовой валюте; проверьте суммы и курсы.

## Идемпотентность постинга

Повторный постинг одной и той же операции можно сделать идемпотентным с помощью ключа:
- в meta use case'а укажите `meta["idempotency_key"] = "some-key"` при вызове `AsyncPostTransaction`.

Повтор с тем же ключом вернёт первый `tx.id` без дублей. Без ключа поведение прежнее.

## Денормализованный быстрый баланс и обороты (I31)

Для исключения полного сканирования журнала при получении текущего баланса и ускорения периодических отчётов добавлены агрегаты:
- account_balances: одна строка на счёт; balance обновляется атомарно (+= Δ), где Δ = сумма(DEBIT) - сумма(CREDIT) в транзакции.
- account_daily_turnovers: одна строка на (счёт, день UTC); debit_total и credit_total аккумулируют дневные обороты.

Алгоритм постинга:
1. Вставить journal + строки.
2. Посчитать Δ per (account, currency) и UPSERT в account_balances.
3. Сгруппировать дебеты/кредиты per (account, day) и UPSERT в account_daily_turnovers.
4. Commit фиксирует всё сразу (атомарность).

Получение баланса:
- Текущий (as_of=None): чтение из account_balances или Decimal('0') если строки нет.
- Исторический (as_of < now): пока fallback к сканированию строк; future: snapshots.

Гонки и идемпотентность:
- Используется один транзакционный scope: SELECT + INSERT/UPDATE исключают потерю дельты.
- Повтор с тем же idempotency_key вернёт старый journal без повторного изменения агрегатов.

Пограничные случаи:
- Новый счёт без транзакций → нет строки в account_balances → баланс = 0.
- Проводки с нулевыми суммами можно пропустить (оптимизация).

Будущее расширение: account_balance_snapshots для быстрых исторических "as_of" запросов.

## Исходный код и импорты для интеграторов

**Доменная логика:**
- `src/py_accountant/domain/quantize.py` — квантизация денег и курсов
- `src/py_accountant/domain/trading_balance.py` — агрегация торгового баланса
- `src/py_accountant/domain/ledger.py` — валидация баланса

**Импорты для интеграторов:**
```python
# Квантизация
from py_accountant.domain.quantize import money_quantize, rate_quantize

# Trading balance
from py_accountant.domain.trading_balance import RawAggregator, ConvertedAggregator

# Use cases
from py_accountant.application.use_cases_async.ledger import AsyncPostTransaction, AsyncGetAccountBalance
from py_accountant.application.use_cases_async.currencies import AsyncCreateCurrency, AsyncSetBaseCurrency
from py_accountant.application.use_cases_async.accounts import AsyncCreateAccount

# Ports (для реализации своего UoW)
from py_accountant.application.ports import AsyncUnitOfWork, Clock
```

## Дополнительно

- Детали dual‑URL (runtime vs migrations) — см. `docs/INTEGRATION_GUIDE.md`.
- Окна времени и отчёты trading — см. `docs/TRADING_WINDOWS.md`.
- FX Audit и TTL — см. `docs/FX_AUDIT.md`.
