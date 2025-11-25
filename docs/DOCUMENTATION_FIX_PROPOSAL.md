# Предложение по исправлению документации py_accountant

**Дата:** 24 ноября 2025  
**Версия RPG:** 1.0.0  
**Статус:** Готово к обсуждению и реализации  
**Автор:** GitHub Copilot

---

## 📋 Содержание

1. [Резюме проблемы](#резюме-проблемы)
2. [Анализ первопричин](#анализ-первопричин)
3. [Предлагаемые решения](#предлагаемые-решения)
4. [План реализации](#план-реализации)
5. [Метрики успеха](#метрики-успеха)

---

## Резюме проблемы

Анализ отчета выявил **10 проблем** в документации, из которых:
- 🔴 **5 критических** — документация описывает API, который не существует или работает иначе
- 🟡 **3 средних** — неполная или неточная информация
- 🟢 **2 минорных** — устаревшие примеры

**Влияние:** Время интеграции увеличивается с ~30 минут до ~4 часов из-за необходимости исследования исходного кода.

**Первопричина:** Документация не обновлялась синхронно с переходом на core-only архитектуру (CORE-01) и удалением SDK-слоя.

---

## Анализ первопричин

### Техническая причина

Проект прошел через **архитектурную трансформацию:**

1. **v0.x** — Наличие SDK-слоя (`py_accountant.sdk.*`)
2. **v0.9.0** (CORE-01) — Удаление SDK, переход на core-only интеграцию
3. **v1.0.0** — Удаление sync API, полный переход на async

**Проблема:** Документация содержит смесь из:
- Устаревших примеров (SDK-слой)
- Неправильных имен модулей (`account` → `accounts`)
- Старых сигнатур (отсутствие информации о реальных параметрах)

### Организационная причина

- ❌ Отсутствие автоматической генерации API-документации (sphinx/mkdocs)
- ❌ Примеры кода не проверяются CI (не запускаются как тесты)
- ❌ Нет single source of truth для API (docstrings не попадают в документацию)

---

## Предлагаемые решения

### 🎯 Стратегия: "Documentation as Code"

**Принцип:** Документация должна быть проверяемой, генерируемой и синхронизированной с кодом.

---

## 1. Немедленные исправления (Priority 1)

### 1.1 Создать API Reference документ

**Создать:** `docs/API_REFERENCE.md`

**Содержание:**

```markdown
# API Reference - Use Cases & DTOs

## Импорты по категориям

### Управление валютами
```python
from py_accountant.application.use_cases_async.currencies import (
    AsyncCreateCurrency,          # Создание валюты
    AsyncGetCurrency,              # Получение валюты по коду
    AsyncListCurrencies,           # Список всех валют
    AsyncSetBaseCurrency,          # Установка базовой валюты
)
```

### Управление счетами
```python
from py_accountant.application.use_cases_async.accounts import (
    AsyncCreateAccount,            # Создание счета
    AsyncGetAccount,               # Получение счета по full_name
    AsyncListAccounts,             # Список всех счетов
)
```

### Операции с транзакциями
```python
from py_accountant.application.use_cases_async.ledger import (
    AsyncPostTransaction,          # Проводка транзакции
    AsyncGetAccountBalance,        # Получение баланса счета
    AsyncListTransactions,         # Список транзакций
)
```

### FX Audit (курсы валют)
```python
from py_accountant.application.use_cases_async.fx_audit import (
    AsyncAddExchangeRateEvent,     # Добавление события курса
    AsyncListExchangeRateEvents,   # История курсов
)
```

### Trading Balance
```python
from py_accountant.application.use_cases_async.trading_balance import (
    AsyncGetTradingBalanceRaw,     # Сырой торговый баланс
    AsyncGetTradingBalanceConverted,  # Конвертированный в базовую валюту
)
```

---

## Use Cases - Детальные сигнатуры

### AsyncCreateAccount

**Конструктор:**
```python
use_case = AsyncCreateAccount(uow: AsyncUnitOfWork)
# ⚠️ НЕ принимает clock!
```

**Вызов:**
```python
async def __call__(
    self,
    full_name: str,          # Иерархическое имя (например "Asset:Bank:USD")
    currency_code: str       # Код валюты (будет нормализован в upper)
) -> AccountDTO
```

**Возвращает:** `AccountDTO` с заполненным `id`

**Исключения:**
- `ValidationError` — неправильный формат `full_name` или `currency_code`
- `ValueError` — валюта не существует ИЛИ счет с таким именем уже есть

**Пример:**
```python
from py_accountant.application.use_cases_async.accounts import AsyncCreateAccount

async with uow_factory() as uow:
    use_case = AsyncCreateAccount(uow)
    account = await use_case(
        full_name="Asset:Bank:USD",
        currency_code="USD"
    )
    print(f"Создан счет {account.id}: {account.full_name}")
```

---

### AsyncPostTransaction

**Конструктор:**
```python
use_case = AsyncPostTransaction(
    uow: AsyncUnitOfWork,
    clock: Clock              # ✅ Clock обязателен!
)
```

**Вызов:**
```python
async def __call__(
    self,
    lines: list[EntryLineDTO],          # Минимум 2 строки
    memo: str | None = None,            # Опциональное описание
    meta: dict[str, Any] | None = None  # Опциональные метаданные
) -> TransactionDTO
```

**Возвращает:** `TransactionDTO` с `id` в формате `"tx:<uuid>"`

**Исключения:**
- `ValidationError` — пустой `lines`, неправильный `side`, невалидная сумма
- `DomainError` — несбалансированная транзакция (дебет ≠ кредит)
- `ValueError` — счет или валюта не найдены

**Пример:**
```python
from decimal import Decimal
from py_accountant.application.dto.models import EntryLineDTO
from py_accountant.application.use_cases_async.ledger import AsyncPostTransaction

lines = [
    EntryLineDTO(
        side="DEBIT",
        account_full_name="Asset:Bank:USD",
        amount=Decimal("100.00"),
        currency_code="USD"
    ),
    EntryLineDTO(
        side="CREDIT",
        account_full_name="Revenue:Sales",
        amount=Decimal("100.00"),
        currency_code="USD"
    ),
]

async with uow_factory() as uow:
    use_case = AsyncPostTransaction(uow, clock)
    tx = await use_case(
        lines=lines,
        memo="Продажа товара",
        meta={"order_id": "12345"}
    )
    await uow.commit()
    print(f"Транзакция {tx.id} проведена")
```

---

### AsyncGetAccountBalance

**Конструктор:**
```python
use_case = AsyncGetAccountBalance(
    uow: AsyncUnitOfWork,
    clock: Clock              # ✅ Clock обязателен!
)
```

**Вызов:**
```python
async def __call__(
    self,
    account_full_name: str,
    as_of: datetime | None = None  # По умолчанию — текущее время
) -> Decimal
```

**Возвращает:** `Decimal` напрямую (НЕ DTO!)

**⚠️ ВАЖНО:** Возвращаемое значение — это `Decimal`, а не объект с полем `.balance`

**Пример:**
```python
from py_accountant.application.use_cases_async.ledger import AsyncGetAccountBalance

async with uow_factory() as uow:
    use_case = AsyncGetAccountBalance(uow, clock)
    balance = await use_case(account_full_name="Asset:Bank:USD")
    
    # ✅ Правильно - balance это уже Decimal
    print(f"Баланс: {balance}")
    
    # ❌ Неправильно
    # print(f"Баланс: {balance.balance}")  # AttributeError!
```

---

## DTOs

### EntryLineDTO

```python
@dataclass(slots=True)
class EntryLineDTO:
    """Строка транзакции (дебет или кредит)"""
    
    side: str                          # 'DEBIT' или 'CREDIT'
    account_full_name: str             # Полное имя счета
    amount: Decimal                    # Сумма (ВСЕГДА положительная!)
    currency_code: str                 # Код валюты
    exchange_rate: Decimal | None = None  # Опционально (автозаполнение)
    meta: dict[str, Any] = field(default_factory=dict)
```

**⚠️ Изменения по сравнению со старой версией:**
- ❌ Нет полей `debit` и `credit`
- ✅ Есть `side` (указывает сторону) + `amount` (всегда положительная сумма)
- ❌ `account` → `account_full_name`
- ❌ `currency` → `currency_code`

**Примеры:**

```python
from decimal import Decimal
from py_accountant.application.dto.models import EntryLineDTO

# Дебет 100 USD
line_debit = EntryLineDTO(
    side="DEBIT",
    account_full_name="Asset:Bank:USD",
    amount=Decimal("100.00"),
    currency_code="USD"
)

# Кредит 100 USD
line_credit = EntryLineDTO(
    side="CREDIT",
    account_full_name="Revenue:Sales",
    amount=Decimal("100.00"),
    currency_code="USD"
)
```

---

### AccountDTO

```python
@dataclass(slots=True)
class AccountDTO:
    """DTO счета"""
    
    id: str                    # Уникальный ID (uuid)
    name: str                  # Имя последнего сегмента
    full_name: str             # Полное иерархическое имя
    currency_code: str         # Код валюты счета
    parent_id: str | None = None  # ID родительского счета
```

---

### TransactionDTO

```python
@dataclass(slots=True)
class TransactionDTO:
    """DTO транзакции"""
    
    id: str                          # Формат "tx:<uuid>"
    occurred_at: datetime            # Время проводки (UTC)
    lines: list[EntryLineDTO]        # Строки транзакции
    memo: str | None = None          # Описание
    meta: dict[str, Any] = field(default_factory=dict)  # Метаданные
```

---

## Какие Use Cases требуют Clock?

### ✅ Требуют Clock:
- `AsyncPostTransaction(uow, clock)` — для timestamp транзакции
- `AsyncGetAccountBalance(uow, clock)` — для вычисления баланса на момент времени

### ❌ НЕ требуют Clock:
- `AsyncCreateAccount(uow)` — только CRUD
- `AsyncGetAccount(uow)` — только чтение
- `AsyncListAccounts(uow)` — только чтение
- `AsyncCreateCurrency(uow)` — только CRUD

**Правило:** Clock нужен только там, где важна временная метка события.

---

## Иерархия исключений

```
Exception
├── DomainError                    # Базовое доменное исключение
│   ├── ValidationError            # Ошибки валидации (формат, constraints)
│   └── (другие доменные ошибки)
└── ValueError                     # Ресурс не найден (стандартное Python)
```

### ValidationError

**Когда бросается:**
- Пустой список `lines` в `AsyncPostTransaction`
- Неправильный `side` в `EntryLineDTO` (не 'DEBIT' и не 'CREDIT')
- Невалидный `full_name` в `AsyncCreateAccount` (пустой, неправильные разделители)
- Неположительная `amount` в `EntryLineDTO`
- Неправильная длина `currency_code` (не 3-10 символов)

### DomainError

**Когда бросается:**
- Несбалансированная транзакция после конвертации в базовую валюту
- Нарушение бизнес-правил (например, больше одной базовой валюты)

### ValueError (стандартный Python)

**Когда бросается:**
- Валюта не существует (`AsyncCreateAccount`)
- Счет не существует (`AsyncPostTransaction`)
- Счет с таким именем уже существует (`AsyncCreateAccount`)

**Пример обработки:**

```python
from py_accountant.domain.errors import ValidationError, DomainError

try:
    tx = await AsyncPostTransaction(uow, clock)(lines=lines)
    await uow.commit()
except ValidationError as e:
    # Ошибка формата данных (400 Bad Request)
    print(f"Неправильный формат: {e}")
except DomainError as e:
    # Нарушение бизнес-правил (422 Unprocessable Entity)
    print(f"Бизнес-правило нарушено: {e}")
except ValueError as e:
    # Ресурс не найден (404 Not Found)
    print(f"Ресурс не существует: {e}")
```

---
```

**Обоснование:**
- ✅ Документ содержит ТОЛЬКО актуальный API
- ✅ Явно указано, какие параметры реально существуют
- ✅ Примеры используют реальные сигнатуры
- ✅ Предупреждения о типичных ошибках
- ✅ Таблица "какие use cases требуют clock"

---

### 1.2 Исправить INTEGRATION_GUIDE.md

**Файл:** `docs/INTEGRATION_GUIDE.md`

**Изменения:**

1. **Секция "Использование как библиотеки"** — заменить все примеры на актуальные

```diff
- from py_accountant.application.use_cases_async.account import AsyncCreateAccount
+ from py_accountant.application.use_cases_async.accounts import AsyncCreateAccount
```

2. **Добавить полный пример интеграции**

```python
# Полный пример создания счетов и проводки транзакции

from decimal import Decimal
from py_accountant.application.use_cases_async.currencies import AsyncCreateCurrency
from py_accountant.application.use_cases_async.accounts import AsyncCreateAccount
from py_accountant.application.use_cases_async.ledger import (
    AsyncPostTransaction,
    AsyncGetAccountBalance,
)
from py_accountant.application.dto.models import EntryLineDTO
from py_accountant.infrastructure.persistence.sqlalchemy.uow import (
    AsyncSqlAlchemyUnitOfWork,
)
from py_accountant.infrastructure.clock import SystemClock

# 1. Создать валюту
async with uow_factory() as uow:
    currency = await AsyncCreateCurrency(uow)(code="USD", is_base=True)
    await uow.commit()

# 2. Создать счета
async with uow_factory() as uow:
    asset = await AsyncCreateAccount(uow)(
        full_name="Asset:Bank:USD",
        currency_code="USD"
    )
    revenue = await AsyncCreateAccount(uow)(
        full_name="Revenue:Sales",
        currency_code="USD"
    )
    await uow.commit()

# 3. Провести транзакцию
lines = [
    EntryLineDTO(
        side="DEBIT",
        account_full_name="Asset:Bank:USD",
        amount=Decimal("100.00"),
        currency_code="USD"
    ),
    EntryLineDTO(
        side="CREDIT",
        account_full_name="Revenue:Sales",
        amount=Decimal("100.00"),
        currency_code="USD"
    ),
]

clock = SystemClock()
async with uow_factory() as uow:
    tx = await AsyncPostTransaction(uow, clock)(
        lines=lines,
        memo="Продажа товара"
    )
    await uow.commit()

# 4. Проверить баланс
async with uow_factory() as uow:
    balance = await AsyncGetAccountBalance(uow, clock)(
        account_full_name="Asset:Bank:USD"
    )
    print(f"Баланс: {balance}")  # Decimal("100.00")
```

**Обоснование:**
- ✅ Работающий end-to-end пример
- ✅ Показывает реальные сигнатуры
- ✅ Можно скопировать и запустить
- ✅ Покрывает типичный use case

---

### 1.3 Исправить README.md

**Файл:** `README.md`

**Изменения:**

1. **Удалить секцию "Использование SDK"** (она уже помечена как историческая, но все равно сбивает с толку)

2. **Заменить на "Quick Start"**

```markdown
## Quick Start

### Установка

```bash
poetry add git+https://github.com/akm77/py_accountant.git@v1.0.0
```

### Минимальный пример

```python
from decimal import Decimal
from py_accountant.application.use_cases_async.accounts import AsyncCreateAccount
from py_accountant.application.use_cases_async.ledger import AsyncPostTransaction
from py_accountant.application.dto.models import EntryLineDTO
from py_accountant.infrastructure.persistence.sqlalchemy.uow import (
    AsyncSqlAlchemyUnitOfWork,
)
from py_accountant.infrastructure.clock import SystemClock

# Настройка (один раз при старте приложения)
def make_uow_factory(database_url: str):
    async def factory():
        return AsyncSqlAlchemyUnitOfWork(database_url)
    return factory

uow_factory = make_uow_factory("postgresql+asyncpg://...")
clock = SystemClock()

# Использование
async with uow_factory() as uow:
    # Создать счет
    account = await AsyncCreateAccount(uow)(
        full_name="Asset:Bank:USD",
        currency_code="USD"
    )
    await uow.commit()

# Детали см. в docs/INTEGRATION_GUIDE.md и docs/API_REFERENCE.md
```

**Обоснование:**
- ✅ Реалистичный минимальный пример
- ✅ Ссылки на полную документацию
- ✅ Не перегружен деталями

---

## 2. Средний приоритет (Priority 2)

### 2.1 Создать ERROR_HANDLING.md

**Создать:** `docs/ERROR_HANDLING.md`

```markdown
# Обработка ошибок в py_accountant

## Иерархия исключений

```
py_accountant.domain.errors.DomainError
├── ValidationError          # Ошибки валидации входных данных
└── [другие доменные ошибки]

ValueError (стандартный Python)  # Ресурс не найден
```

## Классификация ошибок по use case

### AsyncCreateAccount

| Исключение | Причина | HTTP код |
|-----------|---------|----------|
| `ValidationError` | Невалидный `full_name` или `currency_code` | 400 |
| `ValueError` | Валюта не существует | 404 |
| `ValueError` | Счет уже существует | 409 |

### AsyncPostTransaction

| Исключение | Причина | HTTP код |
|-----------|---------|----------|
| `ValidationError` | Пустой `lines` | 400 |
| `ValidationError` | Неправильный `side` | 400 |
| `ValidationError` | Неположительная `amount` | 400 |
| `DomainError` | Несбалансированная транзакция | 422 |
| `ValueError` | Счет не существует | 404 |
| `ValueError` | Валюта не существует | 404 |

## Примеры обработки

### В API endpoint

```python
from fastapi import HTTPException
from py_accountant.domain.errors import ValidationError, DomainError

try:
    tx = await AsyncPostTransaction(uow, clock)(lines=lines)
    await uow.commit()
    return {"transaction_id": tx.id}
except ValidationError as e:
    raise HTTPException(status_code=400, detail=str(e))
except DomainError as e:
    raise HTTPException(status_code=422, detail=str(e))
except ValueError as e:
    raise HTTPException(status_code=404, detail=str(e))
```

### В CLI

```python
from py_accountant.domain.errors import ValidationError, DomainError

try:
    tx = await AsyncPostTransaction(uow, clock)(lines=lines)
    await uow.commit()
except ValidationError as e:
    print(f"❌ Неправильный формат данных: {e}")
    sys.exit(1)
except DomainError as e:
    print(f"❌ Нарушено бизнес-правило: {e}")
    sys.exit(2)
except ValueError as e:
    print(f"❌ Ресурс не найден: {e}")
    sys.exit(3)
```
```

**Обоснование:**
- ✅ Понятная таблица исключений
- ✅ Маппинг на HTTP коды
- ✅ Примеры для разных контекстов

---

### 2.2 Добавить тесты для примеров документации

**Создать:** `tests/docs/test_documentation_examples.py`

```python
"""Тесты проверяют, что примеры из документации работают."""

import pytest
from decimal import Decimal
from py_accountant.application.use_cases_async.accounts import AsyncCreateAccount
from py_accountant.application.use_cases_async.currencies import AsyncCreateCurrency
from py_accountant.application.use_cases_async.ledger import (
    AsyncPostTransaction,
    AsyncGetAccountBalance,
)
from py_accountant.application.dto.models import EntryLineDTO


@pytest.mark.asyncio
async def test_integration_guide_example(async_uow_factory, clock):
    """Пример из INTEGRATION_GUIDE.md должен работать."""
    
    # 1. Создать валюту
    async with async_uow_factory() as uow:
        currency = await AsyncCreateCurrency(uow)(code="USD", is_base=True)
        await uow.commit()
    
    # 2. Создать счета
    async with async_uow_factory() as uow:
        asset = await AsyncCreateAccount(uow)(
            full_name="Asset:Bank:USD",
            currency_code="USD"
        )
        revenue = await AsyncCreateAccount(uow)(
            full_name="Revenue:Sales",
            currency_code="USD"
        )
        await uow.commit()
    
    # 3. Провести транзакцию
    lines = [
        EntryLineDTO(
            side="DEBIT",
            account_full_name="Asset:Bank:USD",
            amount=Decimal("100.00"),
            currency_code="USD"
        ),
        EntryLineDTO(
            side="CREDIT",
            account_full_name="Revenue:Sales",
            amount=Decimal("100.00"),
            currency_code="USD"
        ),
    ]
    
    async with async_uow_factory() as uow:
        tx = await AsyncPostTransaction(uow, clock)(
            lines=lines,
            memo="Продажа товара"
        )
        await uow.commit()
    
    # 4. Проверить баланс
    async with async_uow_factory() as uow:
        balance = await AsyncGetAccountBalance(uow, clock)(
            account_full_name="Asset:Bank:USD"
        )
    
    assert balance == Decimal("100.00")
```

**Обоснование:**
- ✅ Гарантирует, что примеры работают
- ✅ CI сломается, если документация устареет
- ✅ Примеры = документация = тесты (DRY)

---

## 3. Низкий приоритет (Priority 3)

### 3.1 Настроить автогенерацию документации

**Цель:** Использовать docstrings как single source of truth

**Инструменты:** mkdocs + mkdocstrings

**Шаги:**

1. Установить зависимости:

```bash
poetry add --group dev mkdocs mkdocstrings-python mkdocs-material
```

2. Создать `mkdocs.yml`:

```yaml
site_name: py_accountant
theme:
  name: material
  features:
    - navigation.sections
    - toc.integrate

plugins:
  - search
  - mkdocstrings:
      handlers:
        python:
          options:
            show_source: false
            heading_level: 3

nav:
  - Главная: index.md
  - Integration Guide: INTEGRATION_GUIDE.md
  - API Reference:
      - Use Cases: api/use_cases.md
      - DTOs: api/dtos.md
      - Ports: api/ports.md
  - Error Handling: ERROR_HANDLING.md
  - Architecture: ARCHITECTURE_OVERVIEW.md
```

3. Создать `docs/api/use_cases.md`:

```markdown
# Use Cases API

## Accounts

::: py_accountant.application.use_cases_async.accounts.AsyncCreateAccount

::: py_accountant.application.use_cases_async.accounts.AsyncGetAccount

::: py_accountant.application.use_cases_async.accounts.AsyncListAccounts

## Ledger

::: py_accountant.application.use_cases_async.ledger.AsyncPostTransaction

::: py_accountant.application.use_cases_async.ledger.AsyncGetAccountBalance

## Currencies

::: py_accountant.application.use_cases_async.currencies.AsyncCreateCurrency

::: py_accountant.application.use_cases_async.currencies.AsyncSetBaseCurrency
```

4. Добавить в CI:

```yaml
# .github/workflows/docs.yml
name: Deploy Docs

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.13'
      - run: pip install mkdocs mkdocstrings-python mkdocs-material
      - run: mkdocs gh-deploy --force
```

**Обоснование:**
- ✅ Docstrings в коде → автоматическая документация
- ✅ Невозможно забыть обновить документацию
- ✅ Красивый UI (Material theme)
- ✅ Поиск по документации

---

### 3.2 Создать MIGRATION_GUIDE.md

**Создать:** `docs/MIGRATION_GUIDE.md`

```markdown
# Руководство по миграции

## Миграция с SDK-версии (v0.x) на core-only (v1.0+)

### Изменения в импортах

| Старый импорт (v0.x) | Новый импорт (v1.0+) |
|---------------------|---------------------|
| `from py_accountant.sdk.ledger import PostTransaction` | `from py_accountant.application.use_cases_async.ledger import AsyncPostTransaction` |
| `from py_accountant.sdk.accounts import CreateAccount` | `from py_accountant.application.use_cases_async.accounts import AsyncCreateAccount` |
| `from py_accountant.application.use_cases_async.account import ...` | `from py_accountant.application.use_cases_async.accounts import ...` (множественное число!) |

### Изменения API

#### 1. AsyncCreateAccount

**Было:**
```python
await AsyncCreateAccount(uow, clock)(
    full_name="Asset:Bank:USD",
    account_type=AccountType.ASSET,  # ❌ Удалено
    currency=Currency("USD"),         # ❌ Удалено
    description="..."                 # ❌ Удалено
)
```

**Стало:**
```python
await AsyncCreateAccount(uow)(  # ⚠️ clock удален!
    full_name="Asset:Bank:USD",
    currency_code="USD"  # ✅ Просто строка
)
```

#### 2. EntryLineDTO

**Было:**
```python
EntryLineDTO(
    account="Asset:Bank:USD",  # ❌
    debit="100.00",            # ❌
    credit="0",                # ❌
    currency="USD"             # ❌
)
```

**Стало:**
```python
EntryLineDTO(
    side="DEBIT",                    # ✅
    account_full_name="Asset:Bank:USD",  # ✅
    amount=Decimal("100.00"),        # ✅
    currency_code="USD"              # ✅
)
```

#### 3. AsyncGetAccountBalance - возвращаемое значение

**Было:**
```python
balance_dto = await AsyncGetAccountBalance(uow, clock)(...)
print(balance_dto.balance)  # ❌ Был объект
```

**Стало:**
```python
balance = await AsyncGetAccountBalance(uow, clock)(...)
print(balance)  # ✅ Decimal напрямую
```

### Чеклист миграции

- [ ] Обновить импорты (`account` → `accounts`)
- [ ] Удалить параметр `clock` из `AsyncCreateAccount`
- [ ] Заменить `debit`/`credit` на `side` + `amount` в `EntryLineDTO`
- [ ] Изменить обработку результата `AsyncGetAccountBalance` (теперь `Decimal`)
- [ ] Убрать параметры `account_type` и `description` из `AsyncCreateAccount`
- [ ] Заменить `Currency(...)` объекты на `currency_code` строки
- [ ] Запустить тесты

### Автоматизация миграции

Скрипт для автоматического исправления импортов:

```bash
# Исправить импорты
find . -name "*.py" -exec sed -i '' 's/from py_accountant.sdk./from py_accountant.application.use_cases_async./g' {} \;
find . -name "*.py" -exec sed -i '' 's/.use_cases_async.account import/.use_cases_async.accounts import/g' {} \;
```
```

**Обоснование:**
- ✅ Помогает пользователям старых версий
- ✅ Таблица соответствия "было-стало"
- ✅ Чеклист для проверки
- ✅ Скрипт автоматизации

---

## 4. Долгосрочные улучшения

### 4.1 Type stubs для лучшей поддержки IDE

**Проблема:** IDE не всегда правильно определяет типы из docstrings

**Решение:** Создать `.pyi` stub файлы

**Пример:** `src/py_accountant/application/use_cases_async/accounts.pyi`

```python
from py_accountant.application.dto.models import AccountDTO
from py_accountant.application.ports import AsyncUnitOfWork

class AsyncCreateAccount:
    uow: AsyncUnitOfWork
    
    def __init__(self, uow: AsyncUnitOfWork) -> None: ...
    
    async def __call__(
        self,
        full_name: str,
        currency_code: str
    ) -> AccountDTO: ...
```

**Обоснование:**
- ✅ Идеальная поддержка IDE
- ✅ Autocomplete работает на 100%
- ✅ Ошибки типов видны до запуска

---

### 4.2 Интерактивные примеры

**Идея:** Добавить Jupyter notebooks с примерами

**Создать:** `examples/notebooks/`

```
examples/notebooks/
├── 01_getting_started.ipynb
├── 02_transactions.ipynb
├── 03_multicurrency.ipynb
└── 04_reporting.ipynb
```

**Преимущества:**
- ✅ Можно запустить и поэкспериментировать
- ✅ Визуализация результатов
- ✅ Шаг-за-шагом обучение

---

## 5. Обновление RPG-графа

### 5.1 Добавить узел документации

**Файл:** `rpg_py_accountant.yaml`

**Добавить в секцию `nodes.modules`:**

```yaml
- name: "documentation"
  path: "docs/"
  description: "Документация проекта: интеграция, API reference, архитектура, обработка ошибок."
  sub_modules:
    - name: "API_REFERENCE.md"
      description: "Детальный справочник по всем use cases с сигнатурами, примерами и исключениями."
    - name: "INTEGRATION_GUIDE.md"
      description: "Руководство по интеграции py_accountant в проекты: setup, примеры, dual-URL."
    - name: "ERROR_HANDLING.md"
      description: "Классификация ошибок, таблица исключений по use cases, примеры обработки."
    - name: "MIGRATION_GUIDE.md"
      description: "Руководство по миграции с SDK-версии на core-only архитектуру."
```

---

### 5.2 Обновить changelog

**Добавить в `rpg.metadata.changelog`:**

```yaml
- version: "1.1.0"
  date: "2025-11-25"
  changes:
    - "DOC-01: Создан API_REFERENCE.md с актуальными сигнатурами"
    - "DOC-02: Исправлены примеры в INTEGRATION_GUIDE.md"
    - "DOC-03: Обновлен README.md с работающим Quick Start"
    - "DOC-04: Добавлен ERROR_HANDLING.md"
    - "DOC-05: Примеры документации покрыты тестами"
    - "DOC-06: Настроена автогенерация документации (mkdocs)"
```

---

## План реализации

### Фаза 1: Критические исправления (1-2 дня)

**Цель:** Исправить документацию, чтобы новые интеграторы не тратили 4 часа на изучение кода

**Задачи:**
1. ✅ Создать `docs/API_REFERENCE.md` (4 часа)
   - Все use cases с правильными сигнатурами
   - Таблица "какие use cases требуют clock"
   - Структура всех DTOs
   
2. ✅ Исправить `docs/INTEGRATION_GUIDE.md` (2 часа)
   - Заменить все примеры на актуальные
   - Добавить полный end-to-end пример
   
3. ✅ Исправить `README.md` (1 час)
   - Удалить устаревшие примеры SDK
   - Добавить работающий Quick Start
   
4. ✅ Создать `docs/ERROR_HANDLING.md` (2 часа)
   - Таблица исключений по use cases
   - Примеры обработки

**Метрика успеха:** Новый интегратор может начать работу за 30 минут без изучения исходного кода

---

### Фаза 2: Автоматизация (2-3 дня)

**Цель:** Сделать документацию самоподдерживающейся

**Задачи:**
1. ✅ Создать `tests/docs/test_documentation_examples.py` (4 часа)
   - Тесты для всех примеров из документации
   - CI проверяет примеры при каждом PR
   
2. ✅ Настроить mkdocs (4 часа)
   - Автогенерация из docstrings
   - Деплой на GitHub Pages
   - Красивый UI

3. ✅ Создать `docs/MIGRATION_GUIDE.md` (2 часа)
   - Таблица "было-стало"
   - Скрипт автоматизации

**Метрика успеха:** При изменении API документация обновляется автоматически или CI падает

---

### Фаза 3: Улучшения (опционально)

**Цель:** Сделать документацию best-in-class

**Задачи:**
1. ⭕ Type stubs (6 часов)
2. ⭕ Jupyter notebooks (8 часов)
3. ⭕ Видео-туториалы (12 часов)

**Метрика успеха:** py_accountant становится эталоном документирования

---

## Метрики успеха

### Количественные метрики

| Метрика | До | После | Цель |
|---------|-----|-------|------|
| Время первой интеграции | ~4 часа | <30 минут | 8x улучшение |
| Количество вопросов в Issues | — | Отслеживать | Снижение на 50% |
| Coverage примеров тестами | 0% | 100% | CI защищает документацию |
| Время на обновление документации | ~2 часа | ~5 минут | Автогенерация |

### Качественные метрики

- ✅ Все примеры из документации работают without modification
- ✅ Новый интегратор может начать работу без изучения source code
- ✅ IDE показывает правильные типы и сигнатуры
- ✅ CI ломается, если документация устаревает

---

## Риски и митигация

### Риск 1: Документация снова устареет

**Вероятность:** Высокая  
**Влияние:** Высокое

**Митигация:**
1. ✅ Тесты для примеров (CI ломается при изменении API)
2. ✅ Автогенерация из docstrings (single source of truth)
3. ✅ PR checklist: "Обновил ли ты документацию?"

### Риск 2: mkdocs усложнит workflow

**Вероятность:** Средняя  
**Влияние:** Низкое

**Митигация:**
1. ✅ Markdown файлы остаются читаемыми без mkdocs
2. ✅ mkdocs — опциональный инструмент для красивого рендеринга
3. ✅ Не требует изменений в коде

### Риск 3: Много работы для поддержки

**Вероятность:** Средняя  
**Влияние:** Среднее

**Митигация:**
1. ✅ Фаза 1 решает 80% проблем за 1-2 дня
2. ✅ Фаза 2-3 опциональны
3. ✅ Автоматизация снижает нагрузку в будущем

---

## Приоритизация задач

### Must have (Фаза 1)
- 🔴 **Создать API_REFERENCE.md** — критично для интеграторов
- 🔴 **Исправить INTEGRATION_GUIDE.md** — там неправильные примеры
- 🔴 **Исправить README.md** — первое, что видят пользователи

### Should have (Фаза 2)
- 🟡 **Тесты для примеров** — защита от regression
- 🟡 **ERROR_HANDLING.md** — помогает правильно обрабатывать ошибки

### Nice to have (Фаза 3)
- 🟢 **mkdocs** — красиво, но не обязательно
- 🟢 **Type stubs** — IDE и так работает (просто не идеально)
- 🟢 **Jupyter notebooks** — для продвинутых пользователей

---

## Заключение

### Проблема
Документация py_accountant устарела после перехода на core-only архитектуру. Интеграция занимает 4 часа вместо 30 минут.

### Решение
Трехфазный план:
1. **Фаза 1 (must):** Исправить критические ошибки в документации (1-2 дня)
2. **Фаза 2 (should):** Автоматизировать поддержку документации (2-3 дня)
3. **Фаза 3 (nice):** Улучшить UX документации (опционально)

### Ожидаемый результат
- ✅ Время первой интеграции: 4 часа → 30 минут (8x улучшение)
- ✅ Документация защищена тестами (CI ломается при устаревании)
- ✅ Автогенерация из docstrings (single source of truth)
- ✅ py_accountant становится примером хорошей документации

### Следующий шаг
После обсуждения этого предложения:
1. Утвердить план
2. Создать issues для задач Фазы 1
3. Начать реализацию с API_REFERENCE.md

---

**Готов к обсуждению и корректировкам!** 🚀

