# Parity Report — INTERNAL

INTERNAL: этот документ описывает внутренний формат и сценарии согласованности (parity report). Публичной CLI‑команды не предусмотрено; использование — только через async SDK/use cases.

## Назначение
Внутренний отчёт для сверки согласованности валют и торговых остатков в интеграционных сценариях и тестах. Основан на async use cases, без зависимости от legacy CLI.

## Источники истины
- Async use cases: `src/application/use_cases_async/reporting.py`
  - `AsyncGetParityReport` — снимок по валютам (база, последний курс, deviation).
  - `AsyncGetTradingBalanceSnapshotReport` — снимок торгового баланса (raw/detailed) для вспомогательных сверок.
- DTO: `src/application/dto/models.py` (`ParityReportDTO`, `ParityLineDTO`, `TradingBalanceSnapshotDTO`)
- Квантизация: `src/domain/quantize.py` — упомянута минимально (деньги 2 знака, курсы 6 знаков, ROUND_HALF_EVEN)
- Отсутствие публичной команды подтверждается в `src/presentation/cli/main.py` (нет diagnostics/parity команд)

## Формат отчёта (ParityReportDTO)
Поля объекта, возвращаемого `AsyncGetParityReport`:
- `generated_at` — дата/время генерации (ISO8601 UTC, например `2025-11-12T10:00:00Z`).
- `base_currency` — код базовой валюты или `null`.
- `lines[]` — список `ParityLineDTO`:
  - `currency_code` — строка (UPPERCASE).
  - `is_base` — `true/false`.
  - `latest_rate` — строка Decimal или `null` для базы/неизвестного курса (6 знаков после точки при сериализации).
  - `deviation_pct` — строка Decimal или `null` (без дополнительной квантизации; «сырая» точность).
- `total_currencies` — целое число (количество элементов `lines`).
- `has_deviation` — `true/false` (есть ли хотя бы одно ненулевое `deviation_pct`).

Краткий пример JSON (иллюстрация; значения условные):
```json
{
  "generated_at": "2025-11-12T10:00:00Z",
  "base_currency": "USD",
  "total_currencies": 3,
  "has_deviation": true,
  "lines": [
    {"currency_code": "EUR", "is_base": false, "latest_rate": "1.064500", "deviation_pct": "6.4500"},
    {"currency_code": "USD", "is_base": true,  "latest_rate": null,        "deviation_pct": null}
  ]
}
```

### Как считается deviation_pct
Эвристика для небазовых валют при наличии базы: `(latest_rate - 1) * 100`. Для базы и при отсутствии базы — `null`. Значение не округляется дополн��тельно (используется «сырая» точность Decimal).

### Форматы сериализации
- Decimal сериализуем как строку.
- `datetime` в JSON — ISO8601 UTC с `Z` (например, `2025-11-12T10:00:00Z`).
- Денежные величины при сравнениях округляются до 2 знаков; курсы — до 6 знаков (см. `quantize.py`).

## Async пример: получение Parity Report (SDK)
```python
import asyncio
from datetime import UTC, datetime
from infrastructure.persistence.sqlalchemy.uow import AsyncSqlAlchemyUnitOfWork
from application.use_cases_async import AsyncGetParityReport

class Clock:
    def now(self):
        return datetime.now(UTC)

async def main():
    uow = AsyncSqlAlchemyUnitOfWork("sqlite+aiosqlite:///./parity.db")
    async with uow:
        report = await AsyncGetParityReport(uow, Clock())(
            base_only=False,
            codes=None,
            include_dev=True,
        )
        for line in report.lines:
            print(line.currency_code, line.latest_rate, line.deviation_pct)

asyncio.run(main())
```

### Дополнительно: снимок торгового баланса (для сверок)
```python
from application.use_cases_async import AsyncGetTradingBalanceSnapshotReport

async def snapshot_example(uow, clock):
    snapshot = await AsyncGetTradingBalanceSnapshotReport(uow, clock)(detailed=True)
    assert snapshot.mode == "detailed"
    # snapshot.lines_detailed содержит поля net_base и used_rate (6 знаков)
```

## Сравнение с expected (ручная проверка в тесте)
- Пример expected файла: `examples/expected_parity.json`:
  ```json
  {
    "single_currency_basic": {
      "balances": {"Assets:Cash": "100", "Income:Sales": "-100"},
      "base_total": "0"
    }
  }
  ```
- Алгоритм простой сверки:
  1) Загрузить expected JSON.
  2) Получить detailed snapshot через `AsyncGetTradingBalanceSnapshotReport(detailed=True)`.
  3) Сформировать фактические balances по счетам и `base_total` (сумма `net_base` по всем валютам).
  4) При сравнении денежных величин нормализовать к 2 знакам (ROUND_HALF_EVEN). Курсы — как есть (6 знаков). 
  5) Сопоставить строки как строки Decimal п��сле нормализации.

> Примечание: статусы `matched`/`diverged`/`skipped` — концепт внутренних тестов поверх DTO, сам `ParityReportDTO` их не возвращает.

## Типичные сценарии и интерпретац��я полей
- База определена, есть небазовые валюты: `latest_rate` — последний курс, `deviation_pct` показывает отклонение от паритета 1.0, в процентах.
- База отсутствует: `base_currency = null`, `deviation_pct = null` для всех строк.
- В базе строка базы: `is_base = true`, `latest_rate = null`, `deviation_pct = null`.

## Acceptance criteria и проверки
- Документ помечен как INTERNAL и не содержит примеров вызова через публичный CLI.
- Присутствует рабочий async пример `AsyncGetParityReport`.
- Форматы Decimal и datetime описаны.
- Нет упоминаний несуществующих CLI команд.

Проверки в репозитории:
```bash
# Не должно быть упоминаний legacy parity CLI (используйте свой шаблон):
# пример: export LEGACY_PATTERN='<regexp>'; grep -nE "$LEGACY_PATTERN" docs/PARITY_REPORT.md || true
# Должен быть пример с AsyncGetParityReport
grep -n 'AsyncGetParityReport' docs/PARITY_REPORT.md
# INTERNAL дисклеймер
grep -n 'INTERNAL' docs/PARITY_REPORT.md
```
