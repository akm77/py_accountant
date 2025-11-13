# Архитектурный DX+UX аудит пакета py_accountant (GPT‑5)

Дата: 2025-11-13
Аудиторы: системный архитектор, опытный Python‑инженер, бухгалтер‑практик

Источники контекста: rpg_py_accountant.yaml, README.md, docs/INTEGRATION_GUIDE.md, src/application/ports.py, examples/telegram_bot/*, src/infrastructure/persistence/*, pyproject.toml.

## 0) Executive summary

- Сильные стороны: чистая архитектура, async‑only ядро, строгие порты, чёткие DTO и сериализация (Decimal→str, datetime→UTC ISO), хорошая дисциплина UoW per operation, подробные CLI/Telegram примеры.
- Главные точки трения DX: отсутствует стабильный SDK‑слой и фасады (глубокие импорты), нет единого bootstrap (настройки/логирование/UoW), нет ранней runtime‑валидации dual‑URL, нет стандартизованной карты ошибок для интеграторов.
- Главные точки трения UX (бухгалтер): получение остатка счёта и сводки по счетам требует низкоуровневых вызовов; формирование проводок сложно (строгое формирование линий) — нужен упрощённый интерфейс «псевдоязыка» операций.
- Резюме рекомендаций (ROI):
  1) Ввести стабильный SDK‑слой `py_accountant.sdk.*` (uow, bootstrap, settings, logging, errors, json, use_cases). Переэкспорт ключевых фасадов в корневой пакет.
  2) Добавить runtime‑валидацию dual‑URL и preflight‑хелперы.
  3) Стандартизовать публичные исключения и маппинг для бота/HTTP.
  4) UX‑фасады: быстрый баланс счёта, сводка остатков по всем счетам, отчёты trading balance, упрощённый постинг транзакции (парсер/валидатор простого формата).
  5) Документация «SDK surface» + примеры для FastAPI/aiogram/cron; опционально — расширение поддержки Python до 3.11–3.12 при отсутствии 3.13‑критики.

## 1) Соответствие Clean Architecture / RPG‑графу

- Слои соблюдены (Domain → Application → Infrastructure → Presentation). Домены без I/O, use cases async, инфраструктура реализует порты, CLI тонкий.
- RPG‑граф репозитория точен и трассируем: узлы/файлы/тесты описаны, дорожные карты отражают переход на async и удаление sync.
- Разрыв: публичный API пакета (`src/py_accountant/__init__.py`) минимален и не соответствует «интеграционному фасаду» по RPG.

## 2) Публичный API и стабильность

Сейчас:
- Пакет экспортирует только версию и demo‑функцию `add` (см. `src/py_accountant/__init__.py`). Интегратор вынужден импортировать глубоко: `infrastructure.persistence.sqlalchemy.uow.AsyncSqlAlchemyUnitOfWork`, `application.use_cases_async.*`, DTO из `application.dto.models`.

Риски:
- Неочевидна граница «стабильного API», путь импортов хрупок при рефакторингах.

Предлагается (SDK слой):
- `py_accountant.sdk.bootstrap`: `init_app(settings|env) -> AppContext{uow_factory, clock, logger, settings}`
- `py_accountant.sdk.uow`: фабрики UoW по URL/Settings; типы портов re‑export
- `py_accountant.sdk.use_cases`: фасады частых операций (баланс, сводка счетов, постинг, trading balance, FX TTL)
- `py_accountant.sdk.settings`: загрузка env и dual‑URL проверка
- `py_accountant.sdk.logging`: единая конфигурация логгера
- `py_accountant.sdk.errors`: публичные исключения/коды; map_exception
- `py_accountant.sdk.json`: сериализация DTO в JSON (Decimal/datetime)
- Корневой пакет переэкспортирует SDK фасады: `from .sdk import bootstrap, use_cases, ...`

## 3) Удобство интеграции (боты/веб/воркеры)

Сильные стороны:
- Async‑only хорошо сочетается с FastAPI/aiogram/фоновые задачи.
- UoW per operation уже иллюстрирован в INTEGRATION_GUIDE и примерах.

Улучшения DX:
- Bootstrap одним вызовом: `app = sdk.bootstrap.init_app()`
- Единая фабрика UoW с таймаутами/пулом (особенно для asyncpg)
- Преднастроенный JSON‑presenter и error‑mapper
- Консистентные типы возврата и snake_case JSON для внешних API

## 4) Миграции vs runtime (dual URL) — DX и безопасность

- Alembic надёжно принуждает sync URL. Но в runtime возможны конфигурационные ошибки.

Рекомендации:
- `sdk.settings.validate_dual_url(sync_url, async_url) -> None | raises`
- `sdk.env.check_migration_url(url) -> None | raises` (для CI)
- Предупреждение/лог на старте, если async URL не задан и происходит нормализация из sync

## 5) DTO и сериализация

- DTO строгие; правила сериализации определены в README/INTEGRATION_GUIDE.
- Нужен «JSON presenter» для интеграторов, чтобы не повторять преобразования.

Рекомендации:
- `sdk.json.to_dict(dto|list|mapping) -> JSON‑safe`, `sdk.json.to_json(data) -> str`
- Pydantic‑модели для внешних контрактов (минимум) — опционально

## 6) Telegram пример — применимость

- Пример демонстрирует DI, async UoW, базовые команды `/balance`, `/tx`.
- Улучшить: использовать SDK bootstrap и error mapping; добавить примеры сообщений‑ошибок и успешных кейсов с форматированием; вынести парсер транзакций в общий SDK (повторное использование в CLI/API).

## 7) Производительность / масштабирование

- Имеется docs/PERFORMANCE.md; на уровне SDK добавить лёгкие крюки метрик: контекстный лог `use_case_time_ms`, `db_calls`, `uow_time_ms` (feature‑flag через settings).

## 8) Совместимость и зависимости

- Сейчас `python = ">=3.13,<4.0"`. Если нет критичных 3.13‑фич (PEP 695 и т.п.), провести прогон на 3.11–3.12. При зелёных тестах расширить до `>=3.11,<4.0` (увеличение аудитории).

## 9) Качество документации

- Высокий уровень; добавить раздел «SDK surface» в README и INTEGRATION_GUIDE. Свести правила dual‑URL в одном месте и сослаться отовсюду.

## 10) Предлагаемые рефакторинги (ROI‑ordered)

1) Ввести публичный SDK‑слой (минимальная поверхность)
   - Создать файлы:
     - `src/py_accountant/sdk/__init__.py`
     - `src/py_accountant/sdk/bootstrap.py`
     - `src/py_accountant/sdk/uow.py`
     - `src/py_accountant/sdk/settings.py`
     - `src/py_accountant/sdk/logging.py`
     - `src/py_accountant/sdk/errors.py`
     - `src/py_accountant/sdk/json.py`
     - `src/py_accountant/sdk/use_cases.py`
   - Обновить `src/py_accountant/__init__.py`: переэкспорт SDK фасадов (не ломая текущие `__all__`).
   - Тесты: `tests/unit/sdk/test_imports.py`, `tests/unit/sdk/test_json_presenter.py`.

2) Bootstrap и проверка окружения
   - `sdk.settings.load_from_env()` и `sdk.settings.validate_dual_url()`
   - `sdk.bootstrap.init_app(env|settings)` возвращает `AppContext(uow_factory, clock, logger, settings)`
   - Тесты: `tests/unit/sdk/test_settings_dual_url.py`, `tests/integration/sdk/test_bootstrap_sqlite.py`

3) Публичные исключения и error mapping
   - `sdk.errors`: `UserInputError`, `DomainViolation`, `NotFound`, `UnexpectedError` + `map_exception(exc) -> {code, message}`
   - Тесты: `tests/unit/sdk/test_error_mapping.py`

4) JSON presenter
   - `sdk.json`: ручное преобразование Decimal/datetime; ensure snake_case
   - Тесты: `tests/unit/sdk/test_json_decimal_datetime.py`

5) UX‑фасады для бухгалтера
   - `sdk.use_cases.get_account_balance(account_full_name) -> Decimal`
   - `sdk.use_cases.list_accounts_state() -> list[{account, currency, balance}]`
   - `sdk.use_cases.get_trading_balance(base: str|None) -> TradingBalanceDTO`
   - `sdk.use_cases.post_transaction_simple(payload: str|list[str]) -> TransactionId` (использует общий парсер формата `SIDE:Account:Amount:Currency[:Rate]`)
   - Тесты: `tests/integration/sdk/test_simple_posting_and_balances.py`

6) Интеграция примеров и доков
   - Telegram/CLI пример переключить на SDK‑bootstrap и фасады
   - README/INTEGRATION_GUIDE: раздел «SDK surface», примеры FastAPI/aiogram/cron

7) Совместимость Python (опционально)
   - Прогон CI на 3.11/3.12, при успехе — правка `pyproject.toml`, Ruff target‑version

## 11) Дорожная карта (топологический порядок)

1) SDK‑поверхность (каркас пакета + импорты + JSON presenter)
2) Settings/Bootstrap с dual‑URL валидацией
3) Errors mapping (единый контракт)
4) UX‑фасады (баланс, сводка счетов, trading, простой постинг)
5) Обновление примеров (Telegram/CLI) на SDK‑хелперы
6) Документация «SDK surface» и dual‑URL (единое место)
7) (Опционально) Расширение Python до 3.11–3.12; метрики производительности

## 12) Интеграционный рецепт (как должно стать)

Пример для веб/бота/воркера (асинхронно):

```python
from py_accountant.sdk import bootstrap, use_cases

app = bootstrap.init_app()  # читает .env, валидирует dual URL, настраивает логгер
uow_factory = app.uow_factory

async def handler():
    # Баланс счёта
    async with uow_factory():
        bal = await use_cases.get_account_balance("Assets:Cash")
    # Сводка по всем счетам
    async with uow_factory():
        state = await use_cases.list_accounts_state()
    # Простой постинг (две строки, формат понятен бухгалтеру)
    payload = "DEBIT:Assets:Cash:100:USD;CREDIT:Income:Sales:100:USD"
    async with uow_factory():
        tx_id = await use_cases.post_transaction_simple(payload)
    # Trading balance (детализация в базе)
    async with uow_factory():
        trading = await use_cases.get_trading_balance(base_currency="USD")
    return bal, state, tx_id, trading
```

— это снижает объём интеграционного кода и даёт стабильные точки входа.

---

Приложение A. Быстрый чек‑лист соответствия
- Слои разделены: да
- Порты/протоколы ясны: да
- Публичный SDK‑слой: нет (к добавлению в данной дорожной карте)
- Документация по dual‑URL: да (усилить runtime‑проверку в SDK)
- Telegram паттерн UoW per handler: да (усилить bootstrap/error mapping)
- Совместимость Python: 3.13+ (рассмотреть 3.11–3.12)
- Тесты SDK/UX фасадов: нет (запланировать)

Приложение B. Список конкретных изменений по файлам (минимальный срез)
- Добавить пакет `src/py_accountant/sdk/` с файлами: `__init__.py`, `bootstrap.py`, `uow.py`, `settings.py`, `logging.py`, `errors.py`, `json.py`, `use_cases.py`
- Обновить `src/py_accountant/__init__.py`: переэкспортировать `sdk` фасады
- Обновить примеры: `examples/telegram_bot/*` — переход на SDK bootstrap
- Документация: обновить `README.md`, `docs/INTEGRATION_GUIDE.md` (раздел «SDK surface»), добавить `docs/SDK_SURFACE.md`
- Тесты: см. список в разделе 10

Приложение C. UX‑улучшения (детали)
- Баланс счёта: фасад `get_account_balance(name)` возвращает Decimal; формат человекочитаемого ответа в SDK presenter
- Состояние всех счетов: `list_accounts_state()` возвращает список словарей `{account, currency, balance}` отсортированный по иерархии; опционально суммарная строка по валютам
- Торговый баланс: `get_trading_balance(base)` возвращает строгий DTO, плюс helper форматирования «по одной строке на валюту»
- Простой постинг: `post_transaction_simple(payload|lines)` принимает строку/список строк формата `SIDE:Account:Amount:Currency[:Rate]`; использует общий парсер (вынести из примера Telegram) и маппит в `EntryLineDTO`

Приложение D. Тестовое покрытие (что добавить)
- Юнит‑тесты SDK: импорты, JSON, env‑валидация, error mapping
- Интеграционные: bootstrap + sqlite, простой постинг → баланс, сводка счетов
- E2E CLI/Telegram (smoke) через SDK фасады

Приложение E. Опечатки/стилистика
- Исправить оговорки в `rpg_py_accountant.yaml` (перечень см. ARCHITECTURE_AUDIT.md)



