# Migration API Reference

> **Новое в py_accountant 1.2.0**: Комплексная система управления миграциями базы данных

## Обзор

Migration API предоставляет три способа управления схемой базы данных py_accountant:

1. **Программный API (Python)** - Используйте код (рекомендуется для приложений)
2. **CLI команды** - Используйте командную строку (рекомендуется для CI/CD)
3. **Интеграция с Alembic** - Интегрируйте с существующими Alembic-проектами

Все три подхода используют одну и ту же систему миграций (Alembic) и те же файлы миграций.

## Ключевые возможности

- ✅ **Автоматическая инициализация схемы** - Выполняйте миграции программно или через CLI
- ✅ **Валидация версий** - Убедитесь, что код и схема БД синхронизированы
- ✅ **Поддержка PostgreSQL и SQLite** - Работает с обеими СУБД
- ✅ **Async-friendly** - Работает с async SQLAlchemy движками
- ✅ **Type-safe** - Полная типизация и поддержка IDE
- ✅ **Production-ready** - Используется в продакшен-окружениях

## Когда использовать каждый подход

| Подход | Используйте когда | Примеры |
|--------|-------------------|---------|
| **Программный API** | Создаёте приложения (FastAPI, Django, и т.д.) | Миграции при старте, health checks |
| **CLI команды** | CI/CD пайплайны, DevOps workflow | Docker entrypoint, GitHub Actions |
| **Интеграция с Alembic** | У вас уже есть Alembic в проекте | Добавление py_accountant в существующее приложение |

## Быстрый выбор подхода

**Выбирайте программный API если**:
- Вы создаёте новое приложение
- Хотите, чтобы миграции выполнялись автоматически при старте
- Нужен программный контроль над миграциями

**Выбирайте CLI если**:
- Деплоите через Docker/Kubernetes
- У вас есть CI/CD пайплайны
- Предпочитаете явные шаги миграций

**Выбирайте интеграцию с Alembic если**:
- Ваш проект уже использует Alembic
- У вас есть существующие миграции
- Хотите управлять всеми миграциями вместе

---

## Quick Start

### Подход A: Программный API (Python)

#### Базовый пример

```python
from py_accountant.infrastructure.migrations import MigrationRunner
from sqlalchemy.ext.asyncio import create_async_engine

# Создаём движок (async)
engine = create_async_engine("postgresql+asyncpg://user:pass@localhost/mydb")

# Создаём runner
runner = MigrationRunner(engine)

# Выполняем миграции
await runner.upgrade_to_head()

# Проверяем текущую версию
version = await runner.get_current_version()
print(f"Версия схемы БД: {version}")
```

#### Пример с FastAPI

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from py_accountant.infrastructure.migrations import MigrationRunner
from sqlalchemy.ext.asyncio import create_async_engine
import logging

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Выполняем миграции при старте."""
    # Startup: выполняем миграции
    engine = create_async_engine(
        "postgresql+asyncpg://user:pass@localhost/mydb",
        echo=False
    )
    runner = MigrationRunner(engine, echo=True)
    
    logger.info("Выполняем миграции базы данных...")
    await runner.upgrade_to_head()
    logger.info("Миграции завершены")
    
    # Валидируем версию схемы
    from py_accountant import __version_schema__
    current = await runner.get_current_version()
    if current != __version_schema__:
        logger.warning(
            f"Несоответствие версии схемы: current={current}, expected={__version_schema__}"
        )
    
    yield
    
    # Shutdown: очистка
    await engine.dispose()

app = FastAPI(lifespan=lifespan)
```

#### Пример с синхронным движком

```python
from py_accountant.infrastructure.migrations import MigrationRunner
from sqlalchemy import create_engine

# Создаём синхронный движок
engine = create_engine("postgresql+psycopg://user:pass@localhost/mydb")

# Создаём runner (работает и с синхронными движками)
runner = MigrationRunner(engine)

# Выполняем миграции (синхронно)
runner.upgrade_to_head()  # Обратите внимание: без await для синхронных движков
```

---

### Подход B: CLI команды

#### Предварительные требования

```bash
# Установите py_accountant
pip install py-accountant

# Установите переменную окружения с URL базы данных
export DATABASE_URL="postgresql+psycopg://user:pass@localhost/mydb"
```

#### Базовое использование

```bash
# Обновить до последней версии
python -m py_accountant.infrastructure.migrations upgrade head

# Проверить текущую версию
python -m py_accountant.infrastructure.migrations current

# Просмотреть ожидающие миграции
python -m py_accountant.infrastructure.migrations pending

# Просмотреть историю миграций
python -m py_accountant.infrastructure.migrations history
```

#### Пример с Docker

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["python", "app.py"]
```

```bash
#!/bin/bash
# entrypoint.sh

set -e

echo "Выполняем миграции базы данных..."
python -m py_accountant.infrastructure.migrations upgrade head

echo "Запускаем приложение..."
exec "$@"
```

```yaml
# docker-compose.yml
services:
  app:
    build: .
    environment:
      DATABASE_URL: postgresql+psycopg://user:pass@db:5432/mydb
    depends_on:
      db:
        condition: service_healthy
  
  db:
    image: postgres:15
    environment:
      POSTGRES_PASSWORD: pass
      POSTGRES_DB: mydb
    healthcheck:
      test: ["CMD", "pg_isready"]
      interval: 5s
```

---

### Подход C: Интеграция с Alembic

Если вы уже используете Alembic в проекте:

#### Шаг 1: Измените `alembic/env.py`

```python
# alembic/env.py

from alembic import context
from py_accountant.infrastructure.migrations import include_in_alembic

def run_migrations_online():
    """Выполняем миграции в 'online' режиме."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata
        )
        
        # ← Добавьте эту строку
        include_in_alembic(context, table_prefix="", schema=None)
        
        with context.begin_transaction():
            context.run_migrations()

# ... остальная часть env.py
```

#### Шаг 2: Запускайте Alembic как обычно

```bash
alembic upgrade head
```

Миграции py_accountant будут включены автоматически.

---

## Следующие шаги

- См. [API Reference](#api-reference) для детальной документации методов
- См. [CLI Reference](#cli-reference) для всех CLI команд
- См. [Usage Examples](#usage-examples) для более сложных сценариев
- См. [Best Practices](#best-practices) для рекомендаций по использованию в продакшене

---

## API Reference

### MigrationRunner

Основной класс для программного управления миграциями.

#### Конструктор

```python
def __init__(
    self,
    engine: Union[Engine, AsyncEngine],
    alembic_config_path: Optional[str] = None,
    echo: bool = False
)
```

**Параметры**:

- `engine` (`Engine | AsyncEngine`): SQLAlchemy движок (синхронный или асинхронный)
  - Для async движков URL автоматически конвертируется в sync для Alembic
  - Поддерживаемые драйверы: `psycopg` (PostgreSQL), `pysqlite` (SQLite)
  - ⚠️ Async драйверы (`asyncpg`, `aiosqlite`) конвертируются автоматически

- `alembic_config_path` (`str | None`, опционально): Путь к пользовательскому `alembic.ini`
  - По умолчанию: Использует встроенный `alembic.ini.template`
  - Используйте когда нужна кастомная конфигурация Alembic

- `echo` (`bool`, опционально): Включить вывод SQL запросов
  - По умолчанию: `False`
  - Установите в `True` для отладки

**Возвращает**: Экземпляр `MigrationRunner`

**Исключения**:
- `MigrationError`: Если конфигурация некорректна

**Примеры**:

```python
# Async движок (рекомендуется)
from sqlalchemy.ext.asyncio import create_async_engine
engine = create_async_engine("postgresql+asyncpg://localhost/db")
runner = MigrationRunner(engine)

# Синхронный движок
from sqlalchemy import create_engine
engine = create_engine("postgresql+psycopg://localhost/db")
runner = MigrationRunner(engine)

# С включённым echo
runner = MigrationRunner(engine, echo=True)

# С кастомной конфигурацией Alembic
runner = MigrationRunner(engine, alembic_config_path="/path/to/alembic.ini")
```

**Примечания**:
- Thread-safe для синхронных движков
- Для async движков используйте внутри async контекста

---

#### upgrade_to_head()

Обновить базу данных до последней версии миграций.

```python
async def upgrade_to_head(self) -> None  # Для async движков
def upgrade_to_head(self) -> None        # Для sync движков
```

**Параметры**: Нет

**Возвращает**: `None`

**Исключения**:
- `MigrationError`: Если миграция не удалась

**Пример**:

```python
# Async
await runner.upgrade_to_head()

# Sync
runner.upgrade_to_head()
```

**Примечания**:
- Идемпотентен: безопасно вызывать многократно
- Применяет все ожидающие миграции по порядку
- Автоматически создаёт таблицу `alembic_version` при необходимости

---

#### upgrade_to_version()

Обновить базу данных до конкретной версии миграции.

```python
async def upgrade_to_version(self, version: str) -> None  # Async
def upgrade_to_version(self, version: str) -> None        # Sync
```

**Параметры**:

- `version` (`str`): ID целевой ревизии миграции
  - Формат: 4-значная ревизия вида `"0005"` или `"0008"`
  - Должна быть валидной ревизией в директории `versions/`

**Возвращает**: `None`

**Исключения**:
- `MigrationError`: Если версия некорректна или миграция не удалась

**Примеры**:

```python
# Обновить до конкретной версии
await runner.upgrade_to_version("0005")

# Обновить до версии по имени (если знаете полный ID ревизии)
await runner.upgrade_to_version("0005_exchange_rate_events_archive")
```

**Примечания**:
- Применит все миграции до (включительно) целевой версии
- Не выполняет downgrade если текущая версия выше

---

#### downgrade()

Откатить миграции на один или несколько шагов назад.

```python
async def downgrade(
    self,
    steps: int = 1,
    target: Optional[str] = None
) -> None  # Async

def downgrade(
    self,
    steps: int = 1,
    target: Optional[str] = None
) -> None  # Sync
```

**Параметры**:

- `steps` (`int`, опционально): Количество шагов для отката
  - По умолчанию: `1`
  - Пример: `steps=2` откатит две миграции

- `target` (`str | None`, опционально): Целевая ревизия для отката
  - Если указан, `steps` игнорируется
  - Используйте `"base"` для удаления всех миграций

**Возвращает**: `None`

**Исключения**:
- `MigrationError`: Если откат не удался

**Примеры**:

```python
# Откатить один шаг (последнюю миграцию)
await runner.downgrade()

# Откатить два шага
await runner.downgrade(steps=2)

# Откатить до конкретной версии
await runner.downgrade(target="0005")

# Откатить до base (удалить все миграции)
await runner.downgrade(target="base")
```

**⚠️ Предупреждение**:
- Откат может привести к потере данных
- Всегда делайте backup перед откатом в продакшене
- Тестируйте откаты сначала на staging окружении

---

#### get_current_version()

Получить текущую версию схемы базы данных.

```python
async def get_current_version(self) -> Optional[str]  # Async
def get_current_version(self) -> Optional[str]        # Sync
```

**Параметры**: Нет

**Возвращает**:
- `str`: ID текущей ревизии (например, `"0008"`)
- `None`: Если миграции ещё не применялись

**Исключения**: Нет (возвращает `None` при ошибке)

**Примеры**:

```python
# Проверить текущую версию
version = await runner.get_current_version()
if version:
    print(f"Текущая версия: {version}")
else:
    print("Миграции не применялись")

# Сравнить с ожидаемой версией
from py_accountant import __version_schema__
current = await runner.get_current_version()
if current != __version_schema__:
    print(f"Несоответствие версий: {current} != {__version_schema__}")
```

**Примечания**:
- Запрашивает таблицу `alembic_version`
- Возвращает `None` если таблица не существует

---

#### get_pending_migrations()

Получить список ожидающих (ещё не примененных) миграций.

```python
async def get_pending_migrations(self) -> List[str]  # Async
def get_pending_migrations(self) -> List[str]        # Sync
```

**Параметры**: Нет

**Возвращает**:
- `List[str]`: Список ID ожидающих ревизий
- `[]`: Пустой список если все миграции применены

**Исключения**: Нет

**Примеры**:

```python
# Проверить ожидающие миграции
pending = await runner.get_pending_migrations()
if pending:
    print(f"Ожидающие миграции: {', '.join(pending)}")
else:
    print("Все миграции применены")

# Посчитать ожидающие миграции
count = len(await runner.get_pending_migrations())
print(f"Необходимо применить {count} миграций")
```

**Примечания**:
- Возвращает ревизии в порядке применения
- Полезно для health checks

---

#### validate_schema_version()

Валидировать соответствие версии схемы БД ожидаемой версии.

```python
async def validate_schema_version(self, expected: str) -> None  # Async
def validate_schema_version(self, expected: str) -> None        # Sync
```

**Параметры**:

- `expected` (`str`): Ожидаемая версия схемы (например, из `__version_schema__`)

**Возвращает**: `None`

**Исключения**:
- `VersionMismatchError`: Если текущая версия != ожидаемой версии

**Примеры**:

```python
# Валидация при старте
from py_accountant import __version_schema__
try:
    await runner.validate_schema_version(__version_schema__)
    print("Версия схемы валидна")
except VersionMismatchError as e:
    print(f"Несоответствие схемы: {e}")
    # Решить: auto-upgrade или fail

# Валидация и автоматическое обновление
current = await runner.get_current_version()
if current != __version_schema__:
    await runner.upgrade_to_head()
    await runner.validate_schema_version(__version_schema__)
```

**Случаи использования**:
- Валидация при старте в продакшене
- Health checks
- Предотвращение рассинхронизации кода и схемы

---

### Исключения

#### MigrationError

Базовое исключение для всех ошибок связанных с миграциями.

```python
class MigrationError(Exception):
    """Базовое исключение для ошибок миграций."""
    pass
```

**Наследование**: `Exception`

**Вызывается**:
- `MigrationRunner.__init__()` - Некорректная конфигурация
- `upgrade_to_head()` - Ошибка выполнения миграции
- `upgrade_to_version()` - Некорректная версия или ошибка выполнения
- `downgrade()` - Ошибка отката

**Пример**:

```python
from py_accountant.infrastructure.migrations import MigrationError

try:
    await runner.upgrade_to_head()
except MigrationError as e:
    logger.error(f"Миграция не удалась: {e}")
    # Обработать ошибку: повтор, уведомление, откат и т.д.
```

---

#### VersionMismatchError

Вызывается когда версия схемы не соответствует ожидаемой версии.

```python
class VersionMismatchError(MigrationError):
    """Вызывается при несоответствии версии схемы."""
    pass
```

**Наследование**: `MigrationError` → `Exception`

**Вызывается**:
- `validate_schema_version()` - Обнаружено несоответствие версий

**Атрибуты**:
- Наследует стандартные атрибуты исключений

**Пример**:

```python
from py_accountant.infrastructure.migrations import VersionMismatchError
from py_accountant import __version_schema__

try:
    await runner.validate_schema_version(__version_schema__)
except VersionMismatchError as e:
    logger.warning(f"Несоответствие версий: {e}")
    # Решить: auto-upgrade или прервать
    await runner.upgrade_to_head()
```

---

### Интеграция с Alembic

#### include_in_alembic()

Включить миграции py_accountant в существующий Alembic проект.

```python
def include_in_alembic(
    context: AlembicContext,
    table_prefix: str = "",
    schema: Optional[str] = None
) -> None
```

**Параметры**:

- `context` (`alembic.runtime.migration.MigrationContext`): Alembic migration context
  - Передайте из вашего файла `env.py`

- `table_prefix` (`str`, опционально): Префикс для таблиц py_accountant
  - По умолчанию: `""` (без префикса)
  - Пример: `"pyacc_"` → таблицы названы `pyacc_accounts` и т.д.

- `schema` (`str | None`, опционально): Имя PostgreSQL схемы
  - По умолчанию: `None` (схема по умолчанию)
  - Пример: `"accounting"` → таблицы в схеме `accounting`

**Возвращает**: `None`

**Исключения**: Нет

**Пример**:

```python
# alembic/env.py

from alembic import context
from py_accountant.infrastructure.migrations import include_in_alembic

def run_migrations_online():
    connectable = engine_from_config(...)
    
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata
        )
        
        # Включить миграции py_accountant
        include_in_alembic(context)
        
        with context.begin_transaction():
            context.run_migrations()

# С префиксом таблиц
include_in_alembic(context, table_prefix="pyacc_")

# С PostgreSQL схемой
include_in_alembic(context, schema="accounting")

# И префикс и схема
include_in_alembic(context, table_prefix="pyacc_", schema="accounting")
```

**Примечания**:
- Должна вызываться внутри блока `context.configure()`
- Миграции py_accountant выполняются вместе с вашими миграциями
- Поддерживает отдельное отслеживание `alembic_version`

**Случаи использования**:
- Добавление py_accountant в существующее приложение
- Управление несколькими источниками миграций
- Требования к кастомным именам таблиц

---

## CLI Reference

### Проверка установки

```bash
# Проверьте доступность CLI
python -m py_accountant.infrastructure.migrations --help
```

**Ожидаемый вывод**:
```
Usage: python -m py_accountant.infrastructure.migrations [OPTIONS] COMMAND

Commands:
  upgrade    Upgrade database to a specific revision
  downgrade  Downgrade database to a specific revision
  current    Show current database revision
  pending    Show pending migrations
  history    Show migration history
```

---

### Переменные окружения

CLI требует подключения к базе данных через переменную окружения:

```bash
# Вариант 1: Стандартный DATABASE_URL
export DATABASE_URL="postgresql+psycopg://user:pass@localhost:5432/mydb"

# Вариант 2: Специфичный для py_accountant (выше приоритет)
export PYACC__DATABASE_URL="postgresql+psycopg://user:pass@localhost:5432/mydb"
```

**Формат URL**:
- PostgreSQL: `postgresql+psycopg://user:pass@host:port/db`
- SQLite: `sqlite:///path/to/file.db`

**Примечание**: Используйте **sync** драйверы (`psycopg`, `pysqlite`), не async (`asyncpg`, `aiosqlite`)

---

### Команды

#### upgrade [revision]

Обновить базу данных до конкретной ревизии или до head.

**Синтаксис**:
```bash
python -m py_accountant.infrastructure.migrations upgrade [REVISION] [OPTIONS]
```

**Аргументы**:
- `REVISION` (опционально): ID целевой ревизии или `head`
  - По умолчанию: `head` (последняя)
  - Примеры: `0005`, `0008`, `head`

**Опции**:
- `--echo`: Включить вывод SQL (для отладки)

**Примеры**:

```bash
# Обновить до последней версии (наиболее частый случай)
python -m py_accountant.infrastructure.migrations upgrade head

# Обновить до конкретной версии
python -m py_accountant.infrastructure.migrations upgrade 0005

# С выводом SQL
python -m py_accountant.infrastructure.migrations upgrade head --echo

# В Docker entrypoint
#!/bin/bash
echo "Выполняем миграции..."
python -m py_accountant.infrastructure.migrations upgrade head
echo "Запускаем приложение..."
exec python app.py

# В GitHub Actions
- name: Run migrations
  env:
    DATABASE_URL: ${{ secrets.DATABASE_URL }}
  run: python -m py_accountant.infrastructure.migrations upgrade head

# С docker-compose
services:
  app:
    command: >
      sh -c "python -m py_accountant.infrastructure.migrations upgrade head &&
             python app.py"
    environment:
      DATABASE_URL: postgresql+psycopg://user:pass@db/mydb
```

**Коды возврата**:
- `0`: Успех
- `1`: Ошибка (проверьте вывод для деталей)

---

#### downgrade <revision>

Откатить базу данных до конкретной ревизии.

**Синтаксис**:
```bash
python -m py_accountant.infrastructure.migrations downgrade <REVISION> [OPTIONS]
```

**Аргументы**:
- `REVISION` (**обязательно**): ID целевой ревизии или специальные значения
  - ID ревизии: `0005`, `0003` и т.д.
  - `-1`: Откатить один шаг
  - `-2`: Откатить два шага
  - `base`: Удалить все миграции

**Опции**:
- `--echo`: Включить вывод SQL

**Примеры**:

```bash
# Откатить один шаг
python -m py_accountant.infrastructure.migrations downgrade -1

# Откатить два шага
python -m py_accountant.infrastructure.migrations downgrade -2

# Откатить до конкретной версии
python -m py_accountant.infrastructure.migrations downgrade 0005

# Откатить до base (удалить все)
python -m py_accountant.infrastructure.migrations downgrade base

# С echo
python -m py_accountant.infrastructure.migrations downgrade -1 --echo
```

**⚠️ Предупреждение**: Откат может привести к потере данных. Всегда делайте backup!

**Коды возврата**:
- `0`: Успех
- `1`: Ошибка

---

#### current

Показать текущую версию схемы базы данных.

**Синтаксис**:
```bash
python -m py_accountant.infrastructure.migrations current [OPTIONS]
```

**Аргументы**: Нет

**Опции**:
- `--echo`: Включить вывод SQL

**Примеры**:

```bash
# Показать текущую версию
python -m py_accountant.infrastructure.migrations current

# В CI/CD (проверка необходимости миграций)
CURRENT=$(python -m py_accountant.infrastructure.migrations current | grep -oP '\d{4}')
if [ "$CURRENT" != "0008" ]; then
  echo "Требуются миграции"
  exit 1
fi
```

**Формат вывода**:
```
Current version: 0008
```

Если миграции не применялись:
```
Database not initialized
```

**Коды возврата**:
- `0`: Всегда (даже если миграции не применялись)

---

#### pending

Показать ожидающие (ещё не применённые) миграции.

**Синтаксис**:
```bash
python -m py_accountant.infrastructure.migrations pending [OPTIONS]
```

**Аргументы**: Нет

**Опции**:
- `--echo`: Включить вывод SQL

**Примеры**:

```bash
# Показать ожидающие миграции
python -m py_accountant.infrastructure.migrations pending

# Посчитать ожидающие миграции (проверка CI/CD)
PENDING=$(python -m py_accountant.infrastructure.migrations pending | wc -l)
if [ "$PENDING" -gt 0 ]; then
  echo "Предупреждение: $PENDING ожидающих миграций"
fi
```

**Формат вывода**:
```
Pending Migrations
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Revision                             ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ 0006_add_journal_idempotency_key     │
│ 0007_drop_balances_table             │
│ 0008_add_account_aggregates          │
└──────────────────────────────────────┘

3 pending
```

Если нет ожидающих миграций:
```
✓ No pending migrations
```

**Коды возврата**:
- `0`: Всегда

---

#### history

Показать историю миграций (все доступные миграции).

**Синтаксис**:
```bash
python -m py_accountant.infrastructure.migrations history [OPTIONS]
```

**Аргументы**: Нет

**Опции**:
- `--echo`: Включить вывод SQL

**Примеры**:

```bash
# Показать полную историю
python -m py_accountant.infrastructure.migrations history

# Показать историю в CI/CD логах
python -m py_accountant.infrastructure.migrations history
```

**Формат вывода**:
```
<base> -> 0001_initial (head), Initial schema
0001_initial -> 0002_add_is_base_currency, Add is_base_currency flag
0002_add_is_base_currency -> 0003_add_performance_indexes, Add performance indexes
0003_add_performance_indexes -> 0004_add_exchange_rate_events, Add exchange rate events
0004_add_exchange_rate_events -> 0005_exchange_rate_events_archive, Archive exchange rate events
0005_exchange_rate_events_archive -> 0006_add_journal_idempotency_key, Add journal idempotency key
0006_add_journal_idempotency_key -> 0007_drop_balances_table, Drop balances table
0007_drop_balances_table -> 0008_add_account_aggregates (head), Add account aggregates
```

**Коды возврата**:
- `0`: Всегда

---

### Типовые паттерны

#### Health Check

```bash
#!/bin/bash
# Проверка актуальности миграций

CURRENT=$(python -m py_accountant.infrastructure.migrations current | grep -oP '\d{4}')
EXPECTED="0008"

if [ "$CURRENT" = "$EXPECTED" ]; then
  echo "✓ Миграции актуальны"
  exit 0
else
  echo "✗ Несоответствие миграций: current=$CURRENT, expected=$EXPECTED"
  exit 1
fi
```

#### CI/CD Pipeline

```yaml
# .github/workflows/deploy.yml
jobs:
  deploy:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: test_db
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: pip install -r requirements.txt
      
      - name: Check pending migrations
        env:
          DATABASE_URL: postgresql+psycopg://postgres:postgres@localhost:5432/test_db
        run: |
          echo "Проверка ожидающих миграций..."
          python -m py_accountant.infrastructure.migrations pending
      
      - name: Run migrations
        env:
          DATABASE_URL: postgresql+psycopg://postgres:postgres@localhost:5432/test_db
        run: |
          echo "Выполнение миграций..."
          python -m py_accountant.infrastructure.migrations upgrade head
      
      - name: Verify migrations
        env:
          DATABASE_URL: postgresql+psycopg://postgres:postgres@localhost:5432/test_db
        run: |
          echo "Верификация версии схемы..."
          python -m py_accountant.infrastructure.migrations current
          
          # Проверить что не осталось ожидающих миграций
          PENDING=$(python -m py_accountant.infrastructure.migrations pending | grep "No pending" | wc -l)
          if [ "$PENDING" -eq 0 ]; then
            echo "Ошибка: Остались ожидающие миграции"
            exit 1
          fi
      
      - name: Deploy to production
        run: |
          echo "Деплой..."
          # Ваш скрипт деплоя здесь
```

#### Docker Wait-for-DB

```bash
#!/bin/bash
# entrypoint.sh

set -e

# Ожидание базы данных
until python -c "import psycopg; psycopg.connect('$DATABASE_URL')" 2>/dev/null; do
  echo "Ожидание базы данных..."
  sleep 1
done

echo "База данных готова"

# Выполнение миграций
python -m py_accountant.infrastructure.migrations upgrade head

# Запуск приложения
exec "$@"
```

---

## Usage Examples

### Пример 1: FastAPI приложение

Полный пример FastAPI приложения с автоматическими миграциями при старте.

**Файл: `app/main.py`**

```python
from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI, HTTPException
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from py_accountant.infrastructure.migrations import MigrationRunner, MigrationError
from py_accountant import __version_schema__

logger = logging.getLogger(__name__)

# Конфигурация
DATABASE_URL = "postgresql+asyncpg://user:pass@localhost:5432/mydb"

# Настройка базы данных
engine = create_async_engine(DATABASE_URL, echo=False)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Жизненный цикл приложения: выполняем миграции при старте."""
    logger.info("Запуск приложения...")
    
    # Выполнение миграций
    try:
        runner = MigrationRunner(engine, echo=False)
        
        logger.info("Выполнение миграций базы данных...")
        await runner.upgrade_to_head()
        
        # Валидация версии схемы
        current_version = await runner.get_current_version()
        logger.info(f"Текущая версия схемы: {current_version}")
        
        if current_version != __version_schema__:
            logger.warning(
                f"Несоответствие версии схемы: current={current_version}, "
                f"expected={__version_schema__}"
            )
            # Вариант 1: Fail fast
            # raise RuntimeError("Несоответствие версии схемы")
            
            # Вариант 2: Auto-upgrade (используйте с осторожностью)
            logger.info("Автообновление схемы...")
            await runner.upgrade_to_head()
        else:
            logger.info("Версия схемы валидна ✓")
        
    except MigrationError as e:
        logger.error(f"Миграция не удалась: {e}")
        raise RuntimeError(f"Не удалось инициализировать базу данных: {e}")
    
    # Проверка ожидающих миграций (не должно быть после upgrade)
    pending = await runner.get_pending_migrations()
    if pending:
        logger.warning(f"Ожидающие миграции: {pending}")
    
    logger.info("Приложение успешно запущено")
    
    yield
    
    # Shutdown: очистка
    logger.info("Завершение работы...")
    await engine.dispose()
    logger.info("Завершение выполнено")

# Создание приложения
app = FastAPI(
    title="My Accounting App",
    description="FastAPI + py_accountant",
    version="1.0.0",
    lifespan=lifespan
)

@app.get("/health")
async def health_check():
    """Health check endpoint с статусом миграций."""
    async with SessionLocal() as session:
        runner = MigrationRunner(engine)
        current = await runner.get_current_version()
        pending = await runner.get_pending_migrations()
        
        return {
            "status": "healthy" if not pending else "degraded",
            "schema_version": current,
            "expected_version": __version_schema__,
            "pending_migrations": pending
        }

@app.get("/")
async def root():
    return {"message": "Accounting API работает"}

# Запуск: uvicorn app.main:app --reload
```

**Ключевые моменты**:
- Миграции выполняются автоматически при старте
- Валидация версии схемы предотвращает рассинхронизацию
- Health check показывает статус миграций
- Graceful обработка ошибок

---

### Пример 2: CLI приложение с Click

Полное CLI приложение с управлением миграциями.

**Файл: `cli_app/main.py`**

```python
import asyncio
import click
from rich.console import Console
from sqlalchemy.ext.asyncio import create_async_engine
from py_accountant.infrastructure.migrations import MigrationRunner, MigrationError

console = Console()

DATABASE_URL = "postgresql+asyncpg://user:pass@localhost:5432/mydb"

@click.group()
def cli():
    """My Accounting CLI."""
    pass

@cli.command()
def init_db():
    """Инициализировать базу данных (выполнить миграции)."""
    async def _init():
        console.print("[blue]Инициализация базы данных...[/blue]")
        
        engine = create_async_engine(DATABASE_URL)
        runner = MigrationRunner(engine, echo=True)
        
        try:
            # Проверить текущее состояние
            current = await runner.get_current_version()
            if current:
                console.print(f"Текущая версия: [yellow]{current}[/yellow]")
            else:
                console.print("Миграции ещё не применялись")
            
            # Выполнить миграции
            console.print("[blue]Выполнение миграций...[/blue]")
            await runner.upgrade_to_head()
            
            # Подтвердить успех
            new_version = await runner.get_current_version()
            console.print(f"[green]✓[/green] База данных инициализирована (версия: {new_version})")
            
        except MigrationError as e:
            console.print(f"[red]✗ Миграция не удалась: {e}[/red]")
            raise click.Abort()
        finally:
            await engine.dispose()
    
    asyncio.run(_init())

@cli.command()
def check_db():
    """Проверить статус миграций базы данных."""
    async def _check():
        engine = create_async_engine(DATABASE_URL)
        runner = MigrationRunner(engine)
        
        try:
            current = await runner.get_current_version()
            pending = await runner.get_pending_migrations()
            
            console.print(f"Текущая версия: [cyan]{current or 'None'}[/cyan]")
            
            if pending:
                console.print(f"Ожидающие миграции: [yellow]{len(pending)}[/yellow]")
                for migration in pending:
                    console.print(f"  • {migration}")
            else:
                console.print("[green]✓[/green] Все миграции применены")
            
        finally:
            await engine.dispose()
    
    asyncio.run(_check())

@cli.command()
@click.argument('account_code')
def create_account(account_code):
    """Создать новый счёт."""
    async def _create():
        # Сначала убедиться что миграции применены
        engine = create_async_engine(DATABASE_URL)
        runner = MigrationRunner(engine)
        
        pending = await runner.get_pending_migrations()
        if pending:
            console.print("[red]✗ Есть ожидающие миграции. Выполните 'init-db' сначала[/red]")
            raise click.Abort()
        
        # Ваша логика создания счёта здесь
        console.print(f"[green]✓[/green] Счёт {account_code} создан")
        
        await engine.dispose()
    
    asyncio.run(_create())

if __name__ == "__main__":
    cli()

# Запуск: python main.py init-db
#         python main.py check-db
#         python main.py create-account ACC001
```

**Ключевые моменты**:
- Отдельная команда `init-db` для явного контроля миграций
- Команда `check-db` для проверки статуса
- Команды приложения валидируют миграции перед выполнением
- Rich console вывод для обратной связи с пользователем

---

### Пример 3: Telegram бот (aiogram)

Полный Telegram бот с миграциями при старте.

**Файл: `bot/main.py`**

```python
import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from py_accountant.infrastructure.migrations import MigrationRunner, MigrationError
from py_accountant import __version_schema__

# Конфигурация
BOT_TOKEN = "your_bot_token"
DATABASE_URL = "postgresql+asyncpg://user:pass@localhost:5432/mydb"

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# База данных
engine = create_async_engine(DATABASE_URL)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession)

# Бот
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

async def on_startup():
    """Выполнение миграций при старте бота."""
    logger.info("Запуск бота...")
    
    try:
        runner = MigrationRunner(engine)
        
        logger.info("Выполнение миграций базы данных...")
        await runner.upgrade_to_head()
        
        # Валидация схемы
        current = await runner.get_current_version()
        logger.info(f"Версия схемы: {current}")
        
        if current != __version_schema__:
            logger.warning(f"Несоответствие версий: {current} != {__version_schema__}")
            await runner.upgrade_to_head()
        
        logger.info("Бот готов ✓")
        
    except MigrationError as e:
        logger.error(f"Миграция не удалась: {e}")
        raise

async def on_shutdown():
    """Очистка при завершении."""
    logger.info("Завершение работы бота...")
    await engine.dispose()
    logger.info("Завершение выполнено")

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Обработка команды /start."""
    await message.answer("Добро пожаловать в Accounting Bot!")

@dp.message(Command("status"))
async def cmd_status(message: types.Message):
    """Обработка команды /status - показать статус миграций."""
    runner = MigrationRunner(engine)
    current = await runner.get_current_version()
    pending = await runner.get_pending_migrations()
    
    status = (
        f"📊 Статус бота\n\n"
        f"Версия схемы: {current}\n"
        f"Ожидаемая версия: {__version_schema__}\n"
        f"Ожидающие миграции: {len(pending)}"
    )
    
    await message.answer(status)

async def main():
    """Главная точка входа."""
    try:
        # Выполнить startup задачи
        await on_startup()
        
        # Запустить polling
        await dp.start_polling(bot)
        
    finally:
        await on_shutdown()

if __name__ == "__main__":
    asyncio.run(main())

# Запуск: python main.py
```

**Ключевые моменты**:
- Миграции в хуке `on_startup()`
- Валидация схемы перед запуском бота
- Команда `/status` показывает статус миграций
- Graceful shutdown и очистка

---

### Пример 4: Docker + PostgreSQL + CI/CD

Полная настройка Docker с миграциями.

**Файл: `Dockerfile`**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Установка зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование приложения
COPY . .

# Копирование и настройка entrypoint
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["python", "app.py"]
```

**Файл: `docker/entrypoint.sh`**

```bash
#!/bin/bash
set -e

echo "=== Скрипт миграции базы данных ==="

# Ожидание PostgreSQL
echo "Ожидание PostgreSQL..."
while ! nc -z $DB_HOST $DB_PORT; do
  sleep 0.1
done
echo "PostgreSQL готов"

# Выполнение миграций
echo "Выполнение миграций..."
python -m py_accountant.infrastructure.migrations upgrade head --echo

if [ $? -eq 0 ]; then
  echo "✓ Миграции выполнены успешно"
else
  echo "✗ Миграции не удались"
  exit 1
fi

# Верификация версии схемы
echo "Проверка версии схемы..."
python -m py_accountant.infrastructure.migrations current

echo "=== Запуск приложения ==="
exec "$@"
```

**Файл: `docker-compose.yml`**

```yaml
version: '3.8'

services:
  app:
    build: .
    environment:
      DATABASE_URL: postgresql+psycopg://appuser:apppass@db:5432/mydb
      DB_HOST: db
      DB_PORT: 5432
    depends_on:
      db:
        condition: service_healthy
    ports:
      - "8000:8000"
    restart: unless-stopped
  
  db:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: appuser
      POSTGRES_PASSWORD: apppass
      POSTGRES_DB: mydb
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U appuser -d mydb"]
      interval: 5s
      timeout: 5s
      retries: 5
    ports:
      - "5432:5432"

volumes:
  postgres_data:
```

**Файл: `.github/workflows/deploy.yml`**

```yaml
name: Deploy

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: test_db
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
      
      - name: Check pending migrations
        env:
          DATABASE_URL: postgresql+psycopg://postgres:postgres@localhost:5432/test_db
        run: |
          echo "Проверка ожидающих миграций..."
          python -m py_accountant.infrastructure.migrations pending
      
      - name: Run migrations
        env:
          DATABASE_URL: postgresql+psycopg://postgres:postgres@localhost:5432/test_db
        run: |
          echo "Выполнение миграций..."
          python -m py_accountant.infrastructure.migrations upgrade head
      
      - name: Verify migrations
        env:
          DATABASE_URL: postgresql+psycopg://postgres:postgres@localhost:5432/test_db
        run: |
          echo "Верификация версии схемы..."
          python -m py_accountant.infrastructure.migrations current
          
          # Проверить что не осталось ожидающих миграций
          PENDING=$(python -m py_accountant.infrastructure.migrations pending | grep "No pending" | wc -l)
          if [ "$PENDING" -eq 0 ]; then
            echo "Ошибка: Остались ожидающие миграции"
            exit 1
          fi
      
      - name: Deploy to production
        run: |
          echo "Деплой..."
          # Ваш скрипт деплоя здесь
```

**Использование**:

```bash
# Локальная разработка
docker-compose up -d

# Проверка логов
docker-compose logs app

# Ручное выполнение миграций
docker-compose exec app python -m py_accountant.infrastructure.migrations current

# Production деплой
git push origin main  # Запустит GitHub Actions
```

**Ключевые моменты**:
- Логика wait-for-database в entrypoint
- Миграции выполняются перед запуском приложения
- Health checks гарантируют готовность БД
- CI/CD валидирует миграции
- Разделение обязанностей (миграция → проверка → деплой)

---

## Следующие шаги

Продолжите с **Part 2** для:
- Best Practices (Лучшие практики)
- Troubleshooting (Устранение проблем)
- Advanced Topics (Продвинутые темы)
- Migration Development (Разработка миграций)
- Integration with Existing Projects (Интеграция с существующими проектами)

---

**Версия документа**: 1.0.0
**Дата**: 27 ноября 2025
**Совместимость**: py_accountant >= 1.2.0

