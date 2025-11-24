# Шпаргалка проводок (core)

...existing code...
Квантитизация (см. `src/py_accountant/domain/quantize.py`, импорт: `from py_accountant.domain.quantize import money_quantize, rate_quantize`):
- Деньги — 2 знака, ROUND_HALF_EVEN.
- Курсы — 6 знаков, ROUND_HALF_EVEN.
...existing code...
Дополнительно:

- Детали dual‑URL (runtime vs migrations) — см. `docs/INTEGRATION_GUIDE.md`.
- Окна времени и отчёты trading — см. `docs/TRADING_WINDOWS.md`.
- FX Audit и TTL — см. `docs/FX_AUDIT.md`.

Исходный код доменной логики:
- `src/py_accountant/domain/quantize.py`
- `src/py_accountant/domain/trading_balance.py`
- `src/py_accountant/domain/ledger.py`

Импорт для интеграторов:
- `from py_accountant.domain.quantize import money_quantize, rate_quantize`
- `from py_accountant.domain.trading_balance import RawAggregator, ConvertedAggregator`
...existing code...
