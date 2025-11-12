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
`SIDE:ACCOUNT_FULL_NAME:AMOUNT:CURRENCY`
- SIDE: DEBIT | CREDIT
- ACCOUNT_FULL_NAME: полное имя (сегменты через `:`), например `Assets:Cash`
- AMOUNT: положительный Decimal (>0)
- CURRENCY: код валюты (например USD, EUR)

(Поле `rate` больше не используется в CLI для `ledger post` — курс берётся из справочника валют при необходимости.)

## JSON вывод
Почти во всех командах есть флаг `--json` для структурированного вывода:
- Decimal значения сериализуются как строки
- datetime значения (если есть) в ISO8601 UTC (`...Z`)

## Дополнительно
- FX Audit: смотрите `docs/FX_AUDIT.md` (команды: `fx add-event`, `fx list`, `fx ttl-plan` — только план архивации, без выполнения)
- Trading окна и базовая валюта: `docs/TRADING_WINDOWS.md`
- Отчёт согласованности (внутренний инструмент): `docs/PARITY_REPORT.md`

## Ошибки
Коды выхода:
- 0 успех
- 2 Validation/Domain/ValueError (ошибка входных данных / бизнес-правил)
- 1 Unexpected (непредвиденное исключение)
