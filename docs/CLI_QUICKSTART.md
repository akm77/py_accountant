# CLI Quickstart

## Цель
Быстро пройти путь от пустой БД до торгового баланса и примера аудита курсов.

## Шаги
```bash
poetry run alembic upgrade head
poetry run python -m presentation.cli.main currency add USD
poetry run python -m presentation.cli.main currency set-base USD
poetry run python -m presentation.cli.main currency add EUR --rate 1.123400
poetry run python -m presentation.cli.main account add Assets:Cash USD
poetry run python -m presentation.cli.main account add Income:Sales USD
poetry run python -m presentation.cli.main ledger post --line DEBIT:Assets:Cash:100:USD --line CREDIT:Income:Sales:100:USD --memo "Initial sale" --json
poetry run python -m presentation.cli.main ledger balance Assets:Cash --json
poetry run python -m presentation.cli.main trading raw --json
poetry run python -m presentation.cli.main trading detailed --base USD --json
poetry run python -m presentation.cli.main fx add-event EUR 1.123400 --json
poetry run python -m presentation.cli.main fx list --json
poetry run python -m presentation.cli.main fx ttl-plan --retention-days 0 --batch-size 10 --json
poetry run python -m presentation.cli.main diagnostics ping
```

Каждую команду можно запускать повторно; ошибки валидации вернут exit code 2.

## Формат --line
`SIDE:ACCOUNT_FULL_NAME:AMOUNT:CURRENCY[:RATE]`
- SIDE: DEBIT | CREDIT
- ACCOUNT_FULL_NAME: полное имя (сегменты через `:`), например `Assets:Cash`
- AMOUNT: положительный Decimal (>0)
- CURRENCY: код валюты (например USD, EUR)
- RATE (опционально): положительный Decimal (>0), явный курс для строки; если не указан, используется справочник валют/политика домена

Примеры:
- `DEBIT:Assets:Cash:100:USD`
- `CREDIT:Income:Sales:100:USD`
- `DEBIT:Assets:Cash:100:USD:1.000000` (c явным курсом)

## Параметры ledger post
- `--occurred-at <ISO>` — дата/время операции; naive интерпретируется как UTC (будет нормализовано к `...Z`).
- `--lines-file <path.{csv|json}>` — загрузка строк из файла:
  - CSV c заголовками: `side,account,amount,currency[,rate]`
  - JSON-массив строк в формате парсера или объектов `{side,account,amount,currency[,rate]}`
- `--idempotency-key <key>` — идемпотентный постинг: повтор с тем же ключом возвращает исходный `tx.id` без дублей (также можно задать через `--meta idempotency_key=...`) 
- `--meta k=v` — дополнительные поля метаданных; последний дубль побеждает
- `--json` — структурированный вывод

Быстрые примеры:
```bash
# С явной датой и idempotency key
poetry run python -m presentation.cli.main ledger post \
  --line DEBIT:Assets:Cash:100:USD \
  --line CREDIT:Income:Sales:100:USD \
  --occurred-at 2025-01-01T10:00:00 \
  --idempotency-key init-100-usd \
  --json

# Загрузка строк из CSV/JSON
poetry run python -m presentation.cli.main ledger post --lines-file ./tx.csv --json
poetry run python -m presentation.cli.main ledger post --lines-file ./tx.json --json
```

## JSON вывод
Почти во всех командах есть флаг `--json` для структурированного вывода:
- Decimal значения сериализуются как строки
- datetime значения (если есть) — ISO8601 UTC (окончание на `Z` или `+00:00`)

## Дополнительно
- FX Audit: смотрите `docs/FX_AUDIT.md` (команды: `fx add-event`, `fx list`, `fx ttl-plan` — только план архивации, без выполнения)
- Trading окна и базовая валюта: `docs/TRADING_WINDOWS.md`
- Отчёт согласованности (внутренний инструмент): `docs/PARITY_REPORT.md`

## Ошибки
Коды выхода:
- 0 успех
- 2 Validation/Domain/ValueError (ошибка входных данных / бизнес-правил)
- 1 Unexpected (непредвиденное исключение)
