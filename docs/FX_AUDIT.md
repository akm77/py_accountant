# FX Audit (Async)

Документ описывает аудит курсов валют: какие события хранятся, как их добавлять и читать через Python API, и как планировать TTL. Архитектура async-only: работа ведётся через async use cases.

## Назначение
FX Audit фиксирует «события курса» (exchange rate event) — точечные значения курса в момент времени. Это нужно для воспроизводимости расчётов, диагностики и аналитики.

- События добавляются явно через Python API и не изменяются задним числом.
- Чтение событий поддерживает фильтры и пагинацию.
- Политики хранения (TTL) планируются через Python API; исполнение — фоновым воркером.

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

## Python API Usage

**Важно**: Presentation/CLI layer был удалён в версии 1.0.0. Используйте Python API напрямую через async use cases.

### Добавление события курса

Use case: `AsyncAddExchangeRateEvent` из `py_accountant.application.use_cases_async.fx_audit`

```python
from py_accountant.application.use_cases_async.fx_audit import AsyncAddExchangeRateEvent
from decimal import Decimal
from datetime import datetime, UTC

# Инициализация use case
async with uow_factory() as uow:
    use_case = AsyncAddExchangeRateEvent(uow)
    
    # Добавление события курса
    event = await use_case(
        code="USD",
        rate=Decimal("75.50"),
        occurred_at=datetime.now(UTC),
        policy_applied="manual",
        source="manual"  # опционально
    )
    
    print(f"Событие добавлено: ID={event.id}, код={event.code}, курс={event.rate}")
```

**Правила/валидация**:
- `code` — код валюты (нормализуется к верхнему регистру); пустой код → ошибка
- `rate` — Decimal, должен быть > 0
- `occurred_at` — datetime с таймзоной (UTC рекомендуется)
- `policy_applied` — строка, описывающая применённую политику (обычно `"manual"`)
- `source` — опциональный тег источника (по умолчанию `None`)

**Возвращает**: `ExchangeRateEventDTO` с полями:
- `id` — идентификатор события
- `code` — код валюты
- `rate` — курс (Decimal)
- `occurred_at` — время события (datetime)
- `policy_applied` — применённая политика
- `source` — источник (или None)

### Получение списка событий

Use case: `AsyncListExchangeRateEvents` из `py_accountant.application.use_cases_async.fx_audit`

```python
from py_accountant.application.use_cases_async.fx_audit import AsyncListExchangeRateEvents

async with uow_factory() as uow:
    use_case = AsyncListExchangeRateEvents(uow)
    
    # Все события
    events = await use_case()
    
    # Фильтр по валюте
    usd_events = await use_case(code="USD")
    
    # Ограничение количества (последние N событий)
    recent_events = await use_case(code="EUR", limit=10)
    
    for event in events:
        print(f"{event.code}: {event.rate} at {event.occurred_at}")
```

**Параметры**:
- `code` (опционально) — фильтр по коду валюты
- `limit` (опционально) — максимальное количество событий (None = без ограничений)

**Возвращает**: `list[ExchangeRateEventDTO]` (упорядочен по времени, новые сначала)

**Примечания**:
- При `limit=None` может вернуть большой список — используйте осторожно
- События отсортированы по `occurred_at` в обратном порядке (новые первые)

### Планирование TTL для событий курсов

Use case: `AsyncPlanFxAuditTTL` из `py_accountant.application.use_cases_async.fx_audit_ttl`

```python
from py_accountant.application.use_cases_async.fx_audit_ttl import AsyncPlanFxAuditTTL

async with uow_factory() as uow:
    use_case = AsyncPlanFxAuditTTL(uow, clock)
    
    # Планирование архивации старых событий (90 дней)
    plan = await use_case(
        retention_days=90,
        batch_size=1000,
        mode="archive",  # "none", "delete" или "archive"
        limit=None,      # опционально: ограничить количество событий
        dry_run=True     # True = только планирование, без выполнения
    )
    
    print(f"Cutoff date: {plan.cutoff}")
    print(f"События для архивации: {plan.total_old}")
    print(f"Batches: {len(plan.batches)}")
    print(f"Old event IDs (sample): {plan.old_event_ids[:10]}")
```

**Параметры**:
- `retention_days` — окно хранения в днях (>= 0; 0 = удалить все)
- `batch_size` — размер батча для обработки (> 0)
- `mode` — режим: `"none"` (ничего не делать), `"delete"` (удалить), `"archive"` (архивировать и удалить)
- `limit` (опционально) — ограничить количество candidate IDs (None = без ограничений)
- `dry_run` — если `True`, выполнение не изменит данные

**Возвращает**: `FxAuditTTLPlanDTO` с полями:
- `cutoff` — дата отсечки (datetime)
- `mode` — выбранный режим
- `retention_days` — окно хранения
- `batch_size` — размер батча
- `dry_run` — флаг сухого прогона
- `total_old` — общее количество старых событий
- `batches` — список батчей для обработки
- `old_event_ids` — список ID старых событий

### Исполнение TTL

Use case: `AsyncExecuteFxAuditTTL` из `py_accountant.application.use_cases_async.fx_audit_ttl`

**Важно**: Исполнение TTL выполняется фоновым воркером, а не через CLI.

Поведение:
- `mode=none` — никаких действий.
- `mode=delete` — удаление указанных событий батчами.
- `mode=archive` — копирование событий в `exchange_rate_events_archive` c `archived_at`, затем удаление из `exchange_rate_events`.

Контроль целостности плана (в use case):
- `old_event_ids` не пустой для `delete`/`archive`.
- Сумма `batches.limit` должна равняться `total_old` (или 0 при отсутствии кандидатов).
- `batch_size > 0`; `total_old >= 0`.

## Ошибки и валидация (типичные случаи)
Use cases проверяют входные данные. Частые ошибки:
- Неверная ставка: `rate <= 0` или не является Decimal — ValidationError.
- Неверная дата: отсутствие таймзоны или некорректный datetime — ошибка.
- Пагинация: `limit < 0` — ValidationError.
- TTL режим: неизвестный `mode` (не "none"/"delete"/"archive") — ValidationError.
- TTL параметры: `retention_days < 0`, `batch_size <= 0` — ValidationError.
- TTL план/execute: пустые IDs при `delete|archive`; покрытие `batches` не равно `total_old`.

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
- [x] Нет упоминаний устаревших команд CLI.
- [x] Раздел TTL: план через Python API, исполнение — фоновым воркером.
- [x] Примеры JSON содержат нужные поля и форматы (6dp, ISO8601 UTC).
- [x] Зафиксированы режимы TTL: none, delete, archive, и правила ошибок.

## TTL Архитектура
TTL реализуется в два шага: планирование (через `AsyncPlanFxAuditTTL`) и исполнение (через `AsyncExecuteFxAuditTTL` в фоновом воркере). Репозиторий предоставляет только примитивы TTL; оркестрация находится в домене и use cases.

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
2. Python API: создать план через `AsyncPlanFxAuditTTL(retention_days=90, batch_size=1000, mode="archive", dry_run=True)`.
3. Проверить `total_old`, `batches`, `old_event_ids`.
4. Запустить исполнение воркером с `FX_TTL_DRY_RUN=false` через `AsyncExecuteFxAuditTTL`.

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
