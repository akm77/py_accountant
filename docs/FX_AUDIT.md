# FX Audit

## Цель
Фиксировать историю обновлений курсов валют для диагностики, воспроизводимости расчётов и последующего анализа.

- Источник событий: CLI-команды `fx:update` и `fx:batch`, а также обновления из транзакций при наличии политики курса.
- Использование: команда `diagnostics:rates-audit` выводит последние N событий по валютам.

## Схема
Таблица `exchange_rate_events` (Alembic ревизия `0004_add_exchange_rate_events`, см. `alembic/versions/0004_add_exchange_rate_events.py`).

Поля:
- `id` Integer PK — идентификатор события
- `code` String(10) — код валюты (верхний регистр)
- `rate` Numeric(20, 10) — курс (Decimal)
- `occurred_at` DateTime(tz) — время события (UTC)
- `policy_applied` String(64) — применённая политика (например `last_write`, `weighted_average`, `none`)
- `source` String(64) NULL — источник (`cli:fx:update`, `cli:fx:batch`, др.)

Индексы:
- `ix_fx_events_code` — по `code`
- `ix_fx_events_occurred_at` — по `occurred_at`
- `ix_fx_events_code_occurred_at` — составной (`code`, `occurred_at`)

## Пример

Создание базовой валюты и обновление курса:
```bash
poetry run python -m presentation.cli.main currency:add USD
poetry run python -m presentation.cli.main currency:set-base USD
poetry run python -m presentation.cli.main currency:add EUR
poetry run python -m presentation.cli.main fx:update EUR 1.1111
poetry run python -m presentation.cli.main fx:update EUR 1.1234
```

Вывод аудита (JSON):
```bash
poetry run python -m presentation.cli.main diagnostics:rates-audit --json
```
Пример ответа (структура):
```json
{
  "currencies": [
    {
      "code": "EUR",
      "events": [
        {
          "rate": "1.1234000000",
          "occurred_at": "2025-11-10T12:00:00Z",
          "policy": "last_write",
          "source": "cli:fx:update"
        },
        {
          "rate": "1.1111000000",
          "occurred_at": "2025-11-10T11:59:00Z",
          "policy": "last_write",
          "source": "cli:fx:update"
        }
      ],
      "count": 2
    }
  ],
  "limit": null
}
```

## Фильтрация и лимиты

- По конкретному коду (можно повторять флаг `--code`):
```bash
poetry run python -m presentation.cli.main diagnostics:rates-audit --code EUR --json
```
- Лимит на количество событий по каждой валюте:
```bash
poetry run python -m presentation.cli.main diagnostics:rates-audit --limit 1 --json
```
- Совместно:
```bash
poetry run python -m presentation.cli.main diagnostics:rates-audit --code EUR --code GBP --limit 2 --json
```

Замечания по формату:
- `occurred_at` — ISO8601 в UTC с суффиксом `Z`.
- `rate` сериализуется как строка (Decimal → string) для точности.

## Ограничения
- TTL/архивация отсутствуют: объём таблицы будет расти со временем.
- События пишутся «как есть» при успешном обновлении курса; ретроактивные правки не выполняются.

## Политики хранения (TTL/архив)

Начиная с NS20 поддерживаются политики хранения для `exchange_rate_events`.

- Режимы (ENV `FX_TTL_MODE` или флаг `--mode`):
  - `none` — по умолчанию, ничего не делать
  - `delete` — удалять события старше ретенции
  - `archive` — переносить события в таблицу `exchange_rate_events_archive` и удалять из основной
- Параметры:
  - `FX_TTL_RETENTION_DAYS` — число дней хранения (например, 90)
  - `FX_TTL_BATCH_SIZE` — размер партии (например, 1000)
  - `FX_TTL_DRY_RUN` — сухой прогон (ничего не изменять), можно включить CLI-флагом `--dry-run`

Архивная таблица (Alembic 0005): `exchange_rate_events_archive`
- `id` Integer PK
- `source_id` Integer NOT NULL (id из основной таблицы)
- `code` String(10) NOT NULL
- `rate` Numeric(20,10) NOT NULL
- `occurred_at` DateTime(tz) NOT NULL
- `policy_applied` String(64) NOT NULL
- `source` String(64)
- `archived_at` DateTime(tz) NOT NULL

Индексы: `ix_fx_events_archive_code`, `ix_fx_events_archive_occurred_at`, `ix_fx_events_archive_code_occurred_at`, `ix_fx_events_archive_source_id`.

CLI обслуживание:

```bash
poetry run python -m presentation.cli.main maintenance:fx-ttl \
  --mode archive \
  --retention-days 90 \
  --batch-size 1000 \
  --json
```

Пример JSON ответа (поля и формат времени ISO8601 Z):
```json
{
  "scanned": 1234,
  "affected": 1234,
  "archived": 1234,
  "deleted": 1234,
  "mode": "archive",
  "retention_days": 90,
  "batches": 2,
  "started_at": "2025-11-10T00:00:00Z",
  "finished_at": "2025-11-10T00:00:50Z",
  "duration_ms": 50321
}
```

Замечания и ограничения:
- Все сравнения по времени выполняются в UTC; при отсутствии tzinfo время нормализуется к UTC.
- Операция выполняется партиями малых транзакций для минимизации блокировок.
- Поддерживаются SQLite и Postgres без специфичных расширений.
- Рекомендуется запускать в непиковое время.
- Команда `diagnostics:rates-audit` после TTL показывает только актуальные (не удалённые) события.

## Roadmap
- NS17: внешние провайдеры курсов — расширить `source` и добавить health-диагностику.
