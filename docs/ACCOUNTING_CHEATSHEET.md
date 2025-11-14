# Шпаргалка проводок (CLI/SDK)

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

Квантизация (см. `src/domain/quantize.py`):
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

Маппинг ошибок: `py_accountant.sdk.errors.map_exception()` приводит внутренние ValidationError/DomainError/ValueError к дружелюбным публичным ошибкам.

## Идемпотентность постинга

Повторный постинг одной и той же операции можно сделать идемпотентным с помощью ключа:
- CLI: `--idempotency-key my-key` (имеет приоритет над `--meta idempotency_key=...`).
- SDK: положите ключ в `meta["idempotency_key"]` при вызове `post_transaction`.

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
- Текущий (as_of=None): чтение из account_balances или Decimal('0') если строки нет. В SDK: `py_accountant.sdk.use_cases.get_account_balance()` делегирует в AsyncGetAccountBalance и использует этот быстрый путь.
- Исторический (as_of < now): пока fallback к сканированию строк; future: snapshots.

Гонки и идемпотентность:
- Используется один транзакционный scope: SELECT + INSERT/UPDATE исключают потерю дельты.
- Повтор с тем же idempotency_key вернёт старый journal без повторного изменения агрегатов.

Пограничные случаи:
- Новый счёт без транзакций → нет строки в account_balances → баланс = 0.
- Проводки с нулевыми суммами можно пропустить (оптимизация).

Будущее расширение: account_balance_snapshots для быстрых исторических "as_of" запросов.

## Дополнительно

- Детали dual‑URL (runtime vs migrations) — см. `docs/INTEGRATION_GUIDE.md`.
- Окна времени и отчёты trading — см. `docs/TRADING_WINDOWS.md`.
- FX Audit и TTL — см. `docs/FX_AUDIT.md`.
