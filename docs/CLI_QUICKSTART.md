# CLI Quickstart

## Цель
Быстро пройти путь от пустой БД до торгового баланса и аудита курсов.

## Шаги
```bash
poetry run alembic upgrade head
poetry run python -m presentation.cli.main currency:add USD
poetry run python -m presentation.cli.main currency:set-base USD
poetry run python -m presentation.cli.main currency:add EUR
poetry run python -m presentation.cli.main fx:update EUR 1.1111
poetry run python -m presentation.cli.main fx:update EUR 1.1234
poetry run python -m presentation.cli.main diagnostics:rates-audit --json
poetry run python -m presentation.cli.main account:add Assets:Cash USD
poetry run python -m presentation.cli.main account:add Income:Sales USD
poetry run python -m presentation.cli.main tx:post --line DEBIT:Assets:Cash:100:USD --line CREDIT:Income:Sales:100:USD --memo "Initial sale"
poetry run python -m presentation.cli.main trading:detailed --base USD --json
poetry run python -m presentation.cli.main diagnostics:parity-report --expected-file examples/expected_parity.json --json
```

## Формат --line
`side:account:amount:currency[:rate]`
- side: DEBIT|CREDIT
- account: полное имя (колонки через `:`)
- amount: положительный Decimal
- currency: код валюты
- rate (опционально): курс > 0

## Аудит курсов
```bash
poetry run python -m presentation.cli.main diagnostics:rates-audit --json
```

## Parity-report
```bash
poetry run python -m presentation.cli.main diagnostics:parity-report --expected-file examples/expected_parity.json --json
```

## Ошибки
Коды выхода:
- 0 успех
- 2 DomainError (валидация)
- 1 Unexpected

