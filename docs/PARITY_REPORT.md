# Parity Report

## Цель
Проверка внутренней согласованности сценариев относительно ожидаемого файла (expected-file) без legacy движка.

## Формат expected-file
```json
{
  "single_currency_basic": {
    "balances": {
      "Assets:Cash": "100",
      "Income:Sales": "-100"
    },
    "base_total": "0"
  }
}
```

- balances: словарь Account -> Amount (строка Decimal)
- base_total: строка Decimal (сумма converted_balance по базовой валюте)

## Запуск
```bash
poetry run python -m presentation.cli.main diagnostics:parity-report --expected-file examples/expected_parity.json --json
```

## Формат отчёта
```json
{
  "scenarios": [
    {
      "name": "single_currency_basic",
      "status": "matched",
      "differences": {
        "balances": {
          "Assets:Cash": {"expected": "100.00", "new": "100.00", "delta": "0.00"},
          "Income:Sales": {"expected": "-100.00", "new": "-100.00", "delta": "0.00"}
        },
        "trading_balance": {
          "base_total": {"expected": "0.00", "new": "0.00", "delta": "0.00"}
        },
        "rounding_deltas": []
      },
      "tolerance": "0.01"
    }
  ],
  "summary": {"total": 1, "matched": 1, "diverged": 0}
}
```

## Поля
- status: matched|diverged|skipped (при отсутствии expected-file)
- differences.balances.*: expected/new/delta
- differences.trading_balance.base_total.*: expected/new/delta
- differences.rounding_deltas: список расхождений превышающих tolerance

## Границы
- Если отсутствует expected-file → все сценарии skipped с reason legacy_unavailable.
- tolerance управляет чувствительностью к округлению.
