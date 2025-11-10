# Trading Windows

## Цель
Определить, как выбирать диапазон транзакций для расчёта торгового баланса.

## Семантика окна
- Параметры `--start` и `--end` (ISO8601) ограничивают набор транзакций.
- Если не задан `--start`, окно начинается с эпохи (0).
- Если не задан `--end`, окно заканчивается `as_of` или текущим временем.
- `start > end` → DomainError.
- Пустой диапазон → баланс по валютам = 0.

## ASCII таймлайн
```
|----Transactions----|---------------------->
0              start            end(now)
                [  window   ]
```

## Примеры CLI
Все транзакции до текущего момента:
```bash
poetry run python -m presentation.cli.main trading:balance --json
```
Окно с явным диапазоном:
```bash
poetry run python -m presentation.cli.main trading:balance --start 2025-11-10T10:00:00Z --end 2025-11-10T12:00:00Z --json
```
Детализированный баланс (обязателен base):
```bash
poetry run python -m presentation.cli.main trading:detailed --base USD --start 2025-11-10T10:00:00Z --end 2025-11-10T12:00:00Z --json
```
Пустой диапазон:
```bash
poetry run python -m presentation.cli.main trading:detailed --base USD --start 2025-11-10T12:00:00Z --end 2025-11-10T12:00:00Z --json
```
## Граничные случаи
- start == end: окно нулевой длины → пустые строки.
- start > end: ошибка.
- Отсутствие валют (нет транзакций) → пустой список lines.

## Разница между trading:balance и trading:detailed
- `trading:balance` может инферить base, заполняет converted_* частично.
- `trading:detailed` требует `--base`, всегда заполняет converted_debit/credit/balance, добавляет rate_used/rate_fallback.


