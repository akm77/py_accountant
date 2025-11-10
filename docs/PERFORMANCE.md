# Performance

## Цель
Документировать текущий формат метрик производительности и способ запуска профиля.

## Формат JSON отчёта (пример `docs/perf/last_run.json`)
```json
{
  "timestamp": "2025-11-10T12:00:00Z",
  "tx_count": 1000,
  "durations_ms": {
    "post_batch_ms": 250,
    "ledger_list_ms": 40,
    "trading_detailed_ms": 15
  },
  "environment": "test"
}
```

Пояснения:
- tx_count: число транзакций в партии.
- post_batch_ms: суммарное время постинга.
- ledger_list_ms: время выборки журнала с ограничением.
- trading_detailed_ms: время получения детализированного баланса.

## Запуск профиля (план)
Добавить маркер `perf_profile` и тест:
```bash
poetry run pytest -k perf_profile -m perf_profile
```
(На текущий момент используется smoke-тест в `tests/perf/test_cli_perf.py`).

## Интерпретация
- Сравнивайте значения с предыдущими запусками.
- Изменения >20% требуют проверкиcommitов и конфигурации окружения.

## Roadmap метрик
- NS17: метрики внешних FX провайдеров (latency)
- NS18: API latency (FastAPI)
- NS19: экспорт отчётов (время генерации CSV/JSON)
- NS20: TTL jobs (время архивации)

