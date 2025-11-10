# Migration History

## Цель
Зафиксировать эволюцию схемы БД и архитектурные изменения.

## Alembic ревизии
- 0001_initial — базовые таблицы: currencies, accounts, journals, transaction_lines, balances
- 0002_add_is_base_currency — поле `currencies.is_base`
- 0003_add_performance_indexes — индексы производительности
- 0004_add_exchange_rate_events — таблица exchange_rate_events + индексы code/occurred_at

## Удаление legacy py_fledger
- Статус: удалён (физически) — модуль и тесты parity к legacy больше не присутствуют.
- Date: 2025-11-10 (commit REF_PLACEHOLDER)
- Parity теперь работает только через expected-file (internal consistency).

## Parity переход
- Ранее: сравнение py_fledger.Book vs новые use cases.
- Сейчас: diagnostics:parity-report читает сценарии и сверяет с expected.

## Roadmap
- TTL/архив exchange_rate_events (NS20)
- FastAPI слой (NS18)
- Внешние FX провайдеры (NS17)


