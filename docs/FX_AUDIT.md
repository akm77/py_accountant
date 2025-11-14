# FX Audit (Async)

Документ описывает аудит курсов валют: какие события хранятся, как их добавлять и читать из CLI, и как планировать TTL. Архитектура async-only: работа ведётся через async use cases.

## Назначение
FX Audit фиксирует «события курса» (exchange rate event) — точечные значения курса в момент времени. Это нужно для воспроизводимости расчётов, диагностики и аналитики.

- События добавляются явно (CLI или SDK) и не изменяются задним числом.
- Чтение событий поддерживает фильтры и пагинацию.
- Политики хранения (TTL) планируются из CLI; исполнение — фоновым воркером/SDK.

## Таблицы (schema summary)
Основная таблица: `exchange_rate_events` (см. Alembic ревизию `0004_add_exchange_rate_events`).

Поля:
- `id` Integer PK — идентификатор события
- `code` String(10) — код валюты (верхний регистр)
- `rate` Numeric(20, 10) — курс (Decimal)
- `occurred_at` DateTime(tz) — момент события (UTC)
- `policy_applied` String(64) — применённая политика (в текущей реализации: `manual`)
- `source` String(64) NULL — источник/тег (например, `cli`, внешняя система)

Индексы:
- `ix_fx_events_code`
- `ix_fx_events_occurred_at`
- `ix_fx_events_code_occurred_at`

Архивная таблица: `exchange_rate_events_archive` (см. Alembic ревизию `0005_exchange_rate_events_archive`).

Поля:
- `id` Integer PK — идентификатор записи в архиве
- `source_id` Integer NOT NULL — исходный `id` из `exchange_rate_events`
- `code` String(10) NOT NULL
- `rate` Numeric(20, 10) NOT NULL
- `occurred_at` DateTime(tz) NOT NULL
- `policy_applied` String(64) NOT NULL
- `source` String(64)
- `archived_at` DateTime(tz) NOT NULL — время фактической архивации

Индексы:
- `ix_fx_events_archive_code`
- `ix_fx_events_archive_occurred_at`
- `ix_fx_events_archive_code_occurred_at`
- `ix_fx_events_archive_source_id`

## Квантизация курсов
Для отображения курс форматируется до 6 знаков после запятой с банковским округлением (ROUND_HALF_EVEN). Используется helper `rate_quantize` из `src/domain/quantize.py`.

- Правило: 6 дробных знаков, ROUND_HALF_EVEN.
- В БД хранится точность как введена; на выводе — 6 знаков.

## Команды CLI
CLI-группа: `fx` (см. `src/presentation/cli/fx_audit.py`). Все команды async, JSON-вывод включается флагом `--json`.

### add-event — добавить событие
Добавляет новое событие курса (append-only).

Синтаксис:
- `poetry run python -m presentation.cli.main fx add-event CODE RATE [--occurred-at ISO] [--source TEXT] [--json]`

Правила/валидация:
- `CODE` нормализуется к верхнему регистру; пустой код — ошибка.
- `RATE` парсится как Decimal, должен быть > 0.
- `--occurred-at` — ISO8601; если дата без таймзоны, считается UTC; по умолчанию — текущее UTC.
- `policy_applied` устанавливается как `manual`.
- `source` — произвольный тег; по умолчанию `cli`.

JSON-ответ (событие):
```
{
  "id": 42,
  "code": "EUR",
  "rate": "1.123400",
  "occurred_at": "2025-11-12T10:15:30+00:00",
  "policy_applied": "manual",
  "source": "cli"
}
```

### list — список событий
Возвращает список событий с фильтрами и пагинацией.

Синтаксис и параметры:
- `--code CODE` — фильтр по валюте (опционально)
- `--start ISO` — начало окна (включительно, опционально)
- `--end ISO` — конец окна (включительно, опционально)
- `--offset N` — смещение (>= 0; по умолчанию 0)
- `--limit N` — максимум записей (None = без ограничений; 0 = пустой список)
- `--order ASC|DESC` — порядок по `occurred_at` (ASC по умолчанию)
- `--json` — вывод в JSON

Формат JSON:
- Массив объектов события (как в примере для add-event).
- Поля:
  - `rate` — строка с 6 знаками после запятой.
  - `occurred_at` — ISO8601 в UTC (`+00:00`).

Примечания:
- При `limit` не задано список может быть большим — осторожно с памятью.
- `limit=0` вернёт пустой массив без обращения к БД.

### ttl-plan — план TTL
Команда только планирует действия по TTL. Никаких изменений данных не выполняется.

Синтаксис и параметры:
- `--mode MODE` — `none|delete|archive` (по умолчанию `none`)
- `--retention-days D` — окно хранения в днях (>= 0; по умолчанию 90)
- `--batch-size N` — размер батча (> 0; по умолчанию 1000)
- `--limit N` — ограничить количество candidate ID (>= 0; опционально)
- `--dry-run/--no-dry-run` — сухой прогон (по умолчанию `--dry-run`)
- `--json` — вывод плана в JSON

JSON-ответ (план):
```
{
  "cutoff": "2025-11-12T00:00:00+00:00",
  "mode": "archive",
  "retention_days": 90,
  "batch_size": 1000,
  "dry_run": true,
  "total_old": 12345,
  "batches": [{"offset": 0, "limit": 1000}],
  "old_event_ids": [1, 2, 3]
}
```

Подсказка: для машинной обработки всегда добавляйте `--json`.

## TTL исполнение (execute) — вне CLI
Исполнение TTL из CLI недоступно. Выполнение делает фоновый воркер/SDK через use case `AsyncExecuteFxAuditTTL` (см. `src/application/use_cases_async/fx_audit_ttl.py`).

Поведение:
- `mode=none` — никаких действий.
- `mode=delete` — удаление указанных событий батчами.
- `mode=archive` — копирование событий в `exchange_rate_events_archive` c `archived_at`, затем удаление из `exchange_rate_events`.

Контроль целостности плана (в use case):
- `old_event_ids` не пустой для `delete`/`archive`.
- Сумма `batches.limit` должна равняться `total_old` (или 0 при отсутствии кандидатов).
- `batch_size > 0`; `total_old >= 0`.

## Ошибки и валидация (типичные случаи)
CLI и use cases проверяют входные данные. Частые ошибки:
- Неверная ставка: `rate <= 0` или не парсится — ошибка "Invalid rate".
- Неверная дата: плохой ISO-формат — "Invalid datetime".
- Окно времени: `start > end` — ошибка.
- Порядок: `--order` не из `ASC|DESC` — ошибка.
- Пагинация: `offset < 0`, `limit < 0` — ошибка.
- TTL режим: неизвестный `--mode` — ошибка.
- TTL параметры: `retention_days < 0`, `batch_size <= 0` — ошибка.
- TTL план/execute (SDK): пустые IDs при `delete|archive`; покрытие `batches` не равно `total_old`.

## Примеры JSON
Событие:
```
{
  "id": 42,
  "code": "EUR",
  "rate": "1.123400",
  "occurred_at": "2025-11-12T10:15:30+00:00",
  "policy_applied": "manual",
  "source": "cli"
}
```

Результат list (массив объектов):
```
[
  {
    "id": 41,
    "code": "EUR",
    "rate": "1.120000",
    "occurred_at": "2025-11-11T09:00:00+00:00",
    "policy_applied": "manual",
    "source": "cli"
  },
  {
    "id": 42,
    "code": "EUR",
    "rate": "1.123400",
    "occurred_at": "2025-11-12T10:15:30+00:00",
    "policy_applied": "manual",
    "source": "cli"
  }
]
```

План TTL:
```
{
  "cutoff": "2025-11-12T00:00:00+00:00",
  "mode": "archive",
  "retention_days": 90,
  "batch_size": 1000,
  "dry_run": true,
  "total_old": 12345,
  "batches": [{"offset": 0, "limit": 1000}],
  "old_event_ids": [1, 2, 3]
}
```

## Ограничения и замечания
- События иммутабельны: обновление/редактирование не поддерживается, только добавление.
- Архивация переносит запись в архив без изменения `rate`; затем из основной таблицы запись удаляется (для `archive`).
- При вводе `rate` с лишними знаками хранится исходная точность; на выводе — форматирование до 6 знаков.
- Даты без tz интерпретируются как UTC; все ответы возвращают время в ISO8601 UTC (`+00:00`).
- Режим `none` + dry-run даёт инертный план (нулевые мутации).

## Ссылки
- Архитектура: `docs/ARCHITECTURE_OVERVIEW.md` (async-only, TTL план vs execute)
- Квантизация: `src/domain/quantize.py` (rate=6dp, ROUND_HALF_EVEN)
- Переменные окружения: README (ENV переменные) и INTEGRATION_GUIDE (dual-URL + TTL)
- TTL Архитектура: см. также `docs/INTEGRATION_GUIDE.md` (секция TTL конфигурация).

---
Мини-чеклист (внутренний):
- [x] Нет упоминаний устаревших команд.
- [x] Раздел TTL: план в CLI, исполнение — вне CLI.
- [x] Примеры JSON содержат нужные поля и форматы (6dp, ISO8601 UTC).
- [x] Зафиксированы режимы TTL: none, delete, archive, и правила ошибок.

## TTL Архитектура
TTL реализуется в два шага: планирование (CLI `fx ttl-plan`) и исполнение (воркер/SDK). Репозиторий предоставляет только примитивы TTL; оркестрация находится в домене и use cases.

Слои:
- Примитивы TTL репозитория: `list_old_events(cutoff)`, `archive_events(rows)`, `delete_events_by_ids(ids)`.
- Доменный сервис: `FxAuditTTLService` (`make_cutoff`, `identify_old`, `batch_plan`).
- Use cases: `AsyncPlanFxAuditTTL` (формирует план) и `AsyncExecuteFxAuditTTL` (валидирует и исполняет план, вызывает примитивы).

Таблица режимов (`FX_TTL_MODE`):
| Режим | Действия | Мутации | Требуются old_event_ids | Архивация |
|-------|----------|---------|-------------------------|-----------|
| none  | Нет      | Нет     | Нет                     | Нет       |
| delete| Удаление | Да      | Да                      | Нет       |
| archive| Архив + удаление | Да | Да                  | Да        |

Целостность плана контролируется в `AsyncExecuteFxAuditTTL`:
- Сумма `limit` по батчам покрывает `total_old` (или `total_old=0`).
- Для `delete|archive` список `old_event_ids` не пуст.
- `batch_size > 0`, `retention_days >= 0`.

Псевдокод (оркестрация TTL):
```
cutoff = now() - retention_days
plan = AsyncPlanFxAuditTTL(uow, clock)(retention_days, batch_size, mode, limit, dry_run)
for batch in plan.batches:
    if plan.mode == "archive" and not plan.dry_run:
        archived += archive_events(batch.rows, archived_at=now())
    if plan.mode in ("delete", "archive") and not plan.dry_run:
        deleted += delete_events_by_ids(batch.ids)
```

## Переменные окружения (FX TTL)
- `FX_TTL_MODE` — `none|delete|archive` (по умолчанию `none`).
- `FX_TTL_RETENTION_DAYS` — окно хранения в днях (например `90`).
- `FX_TTL_BATCH_SIZE` — размер батча (`>0`, по умолчанию `1000`).
- `FX_TTL_DRY_RUN` — `true|false`; при `true` мутации пропускаются.

Рекомендуемый безопасный запуск:
1. `FX_TTL_MODE=archive` и `FX_TTL_DRY_RUN=true`.
2. CLI: `fx ttl-plan --retention-days 90 --batch-size 1000 --mode archive --json`.
3. Проверить `total_old`, `batches`, `old_event_ids`.
4. Запустить исполнение воркером с `FX_TTL_DRY_RUN=false`.

## Глоссарий (TTL)
- retention_cutoff — `now() - retention_days` (UTC).
- batch — группа событий (до `FX_TTL_BATCH_SIZE`).
- primitives — минимальные методы репозитория без бизнес-логики.
- orchestration — последовательное применение примитивов на основе плана.
- dry_run — режим, когда `archive_events` и `delete_events_by_ids` не вызываются.

## Терминология
Используем:
- «примитивы TTL репозитория» для `list_old_events`, `archive_events`, `delete_events_by_ids`.
- «оркестрация TTL» только для логики план→исполнение в домене/use cases.
