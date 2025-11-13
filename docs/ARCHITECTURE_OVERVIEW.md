# Architecture Overview

Коротко: ядро async-only; порты объявлены как Protocol-интерфейсы; домен чистый (без I/O); квантизация фиксирована: money=2dp, rate=6dp, ROUND_HALF_EVEN; Trading Detailed требует базовую валюту, а для небазовой — положительный курс; в CLI для FX TTL есть только план, исполнение делает воркер/SDK.

- Репозиторий: py_accountant (Poetry)
- Диаграмма: docs/ARCHITECTURE_OVERVIEW.puml (PlantUML) — поток CLI → Async Use Cases → Ports → Infra (Async UoW + Repos) → DB; Domain отдельно, без I/O.

## Слои системы

- Presentation (CLI)
  - Typer-команды — тонкие контроллеры: парсят флаги/аргументы, валидируют примитивы, вызывают async use cases, печатают JSON или «человеческие» строки.
  - Конвенции вывода: JSON в snake_case; Decimal → строка; datetime → ISO8601 UTC (Z или +00:00).
- Application (Use Cases)
  - Только async use cases: currencies/accounts/ledger/trading/fx audit/ttl plan/ttl execute.
  - Работают через порты (AsyncUnitOfWork, репозитории, Clock); I/O выполняется только адаптерами инфраструктуры.
- Domain (Чистая модель)
  - Value-объекты и сервисы агрегации (trading raw/converted, FX‑политики), никаких обращений к БД/сетям/файлам.
  - Квантизация централизована: money=2 знака, rate=6 знаков, округление ROUND_HALF_EVEN (см. `src/domain/quantize.py`).
- Infrastructure (Адаптеры)
  - AsyncSqlAlchemyUnitOfWork и SQLAlchemy-репозитории (CRUD-only), конфиг, логирование.
  - Alembic используется только для миграций и работает с синхронным драйвером (см. `alembic/env.py`).

## Async-only и миграции

- Весь публичный runtime — асинхронный (CLI вызывает async use cases). Sync UoW/репозитории удалены.
- Исключение — Alembic: для миграций применяется синхронный URL/драйвер. В `alembic/env.py` есть явные проверки на запрет async-драйверов.

## Порты (Ports) и контракты

- Порты объявлены в `src/application/ports.py` как Async* Protocols:
  - AsyncUnitOfWork: собирает async-репозитории (accounts, currencies, transactions, exchange_rate_events) и транзакционные границы.
  - Репозитории: строго CRUD-only, без доменной логики.
  - Clock: предоставляет `now()` для детерминизма времени.

## Поток данных

1) CLI (Typer) → 2) Use Case (async) → 3) Порты (Protocol) → 4) Инфраструктура (Async UoW + репозитории) → 5) База данных.

Таблицы БД: `accounts`, `currencies`, `transactions`, `transaction_lines`, `exchange_rate_events`, `exchange_rate_events_archive`.

Сериализация наружу: Decimal → строка; datetime → ISO8601 UTC; JSON-ключи — snake_case.

## Квантизация (Quantization)

Источник истины: `src/domain/quantize.py`.
- Деньги: 2 знака после запятой, ROUND_HALF_EVEN — функция `money_quantize(x)`.
- FX‑курс: 6 знаков после запятой, ROUND_HALF_EVEN — функция `rate_quantize(x)`.
Эти функции не изменяют глобальный Decimal‑контекст (используют локальный).

Небольшой пример DTO-формата (строки для Decimal):
```
{
  "currency_code": "USD",
  "debit": "10.00",
  "credit": "0.00",
  "net": "10.00"
}
```

## Trading: raw vs detailed

- Raw: агрегирует по валютам без конверсии (см. `domain/trading_balance.RawAggregator`).
- Detailed: агрегирует и конвертирует в базовую валюту (см. `domain/trading_balance.ConvertedAggregator`).
  - Требования:
    - Базовая валюта обязана быть задана: явно (`--base`) или выбрана из справочника валют (единственная is_base=true).
    - Для базовой валюты `used_rate = 1`.
    - Для любой небазовой валюты курс должен существовать и быть > 0; иначе ValidationError.
  - Квантизация: суммы — 2 знака; `used_rate` — 6 знаков; суммы в базе также квантуются до 2 знаков.

Пример одной строки Detailed (JSON):
```
{
  "currency_code": "EUR",
  "base_currency_code": "USD",
  "debit": "100.00",
  "credit": "0.00",
  "net": "100.00",
  "used_rate": "1.250000",
  "debit_base": "125.00",
  "credit_base": "0.00",
  "net_base": "125.00"
}
```

## FX Audit и TTL

- События курсов хранятся в `exchange_rate_events`, архив — в `exchange_rate_events_archive` (индексация по времени/коду).
- TTL:
  - В CLI доступно только планирование: `fx ttl-plan` (формирует `cutoff`, `batches`, `old_event_ids`, без побочных эффектов).
  - Исполнение (delete/archive) делает воркер/SDK через use case `AsyncExecuteFxAuditTTL` — CLI не вызывает execute.

Мини‑пример плана (JSON):
```
{
  "cutoff": "2025-11-12T00:00:00+00:00",
  "mode": "archive",
  "retention_days": 90,
  "batch_size": 1000,
  "dry_run": true,
  "total_old": 12345,
  "batches": [{"offset": 0, "limit": 1000}, {"offset": 1000, "limit": 1000}],
  "old_event_ids": [1,2,3]
}
```

## Ошибки и инварианты

- Presentation: парсинг параметров — `ValidationError`/`ValueError` → код выхода 2; неожиданные ошибки → код 1 (см. `presentation/cli/main.py`).
- Application: проверка окон времени (start <= end), форматов meta, наличие базы, корректность режимов TTL и пр.
- Domain: строгая валидация кодов валют, сторон проводок, положительности сумм и курсов; никакого доступа к I/O.

## Alembic (только sync)

- Миграции запускаются с синхронным URL/драйвером (например, `sqlite+pysqlite`, `postgresql+psycopg`).
- В `alembic/env.py` при попытке передать async‑драйвер происходит отказ с понятной ошибкой.

## Диаграмма архитектуры (PlantUML)

Файл: `docs/ARCHITECTURE_OVERVIEW.puml`.
- Содержит поток: CLI → Async Use Cases → Ports → Infra (Async UoW + Repos) → DB и отдельный чистый Domain.
- Явно отмечено: `fx ttl-plan` доступен в CLI; `ttl execute` — только через воркер/SDK.

Как отрендерить (варианты):
- Через PlantUML CLI:
  - `plantuml -tsvg docs/ARCHITECTURE_OVERVIEW.puml`
- Через IDE/плагин (IntelliJ/VS Code) — открыть `.puml` и выбрать предпросмотр/рендер.

## Навигация по исходникам (источники истины)

- CLI: `src/presentation/cli/main.py`, `src/presentation/cli/*.py`
- Domain: `src/domain/quantize.py`, `src/domain/trading_balance.py`
- Use cases (async): `src/application/use_cases_async/trading_balance.py`, `src/application/use_cases_async/fx_audit_ttl.py`
- Ports: `src/application/ports.py`
- Alembic (sync-only): `alembic/env.py`

## Ключевые тезисы (TL;DR)

- Async-only: все публичные пути — асинхронные. Sync UoW/репозитории удалены.
- Domain чистый, без I/O и кешей. Квантизация: money=2dp, rate=6dp, ROUND_HALF_EVEN.
- Trading Detailed: base обязателен; `used_rate=1` только для базовой; для небазовой без положительного курса — ValidationError.
- FX TTL: CLI — только план (`ttl-plan`); исполнение — через use case/SDK воркер (`AsyncExecuteFxAuditTTL`).
- Alembic использует только sync‑драйверы и применяется лишь для миграций.
