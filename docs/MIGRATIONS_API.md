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

## Best Practices

### Startup Validation

#### Always Validate Schema Version

```python
from py_accountant import __version_schema__
from py_accountant.infrastructure.migrations import MigrationRunner, VersionMismatchError

async def validate_database():
    """Validate database schema on application startup."""
    runner = MigrationRunner(engine)
    
    try:
        await runner.validate_schema_version(__version_schema__)
        logger.info("✓ Schema version validated")
    except VersionMismatchError as e:
        logger.error(f"Schema version mismatch: {e}")
        
        # Option 1: Fail fast (recommended for production)
        raise RuntimeError("Database schema outdated. Run migrations first.")
        
        # Option 2: Auto-upgrade (use with caution)
        # logger.warning("Auto-upgrading schema...")
        # await runner.upgrade_to_head()
```

**Recommendation**: 
- ✅ **Fail fast in production** - Prevents running with wrong schema
- ⚠️ **Auto-upgrade in development** - Convenience vs. safety tradeoff

---

#### Check Pending Migrations

```python
async def check_migrations():
    """Check for pending migrations and log warning."""
    runner = MigrationRunner(engine)
    pending = await runner.get_pending_migrations()
    
    if pending:
        logger.warning(f"Pending migrations: {', '.join(pending)}")
        logger.warning("Database schema may be out of date")
        # Optionally: send alert, block startup, etc.
    else:
        logger.info("✓ All migrations applied")
```

---

#### Graceful Degradation

```python
async def startup_with_fallback():
    """Startup with graceful migration error handling."""
    try:
        runner = MigrationRunner(engine)
        await runner.upgrade_to_head()
    except MigrationError as e:
        logger.error(f"Migration failed: {e}")
        
        # Check if database is accessible
        current = await runner.get_current_version()
        if current:
            logger.info(f"Database accessible (version: {current})")
            logger.warning("Continuing with existing schema (degraded mode)")
            # Application continues but may have limited functionality
        else:
            logger.critical("Database not accessible")
            raise RuntimeError("Cannot start without database")
```

---

### Error Handling

#### Catch and Log Migration Errors

```python
from py_accountant.infrastructure.migrations import MigrationError

try:
    await runner.upgrade_to_head()
except MigrationError as e:
    logger.error(f"Migration failed: {e}", exc_info=True)
    
    # Send alert
    await send_alert(f"Migration failed in {environment}: {e}")
    
    # Optionally: attempt rollback
    # await runner.downgrade(steps=1)
    
    raise
```

---

#### Implement Retry Logic

```python
async def run_migrations_with_retry(max_attempts: int = 3):
    """Run migrations with retry logic."""
    runner = MigrationRunner(engine)
    
    for attempt in range(1, max_attempts + 1):
        try:
            logger.info(f"Migration attempt {attempt}/{max_attempts}")
            await runner.upgrade_to_head()
            logger.info("✓ Migrations completed")
            return
        except MigrationError as e:
            logger.warning(f"Migration attempt {attempt} failed: {e}")
            
            if attempt < max_attempts:
                await asyncio.sleep(5)  # Wait before retry
            else:
                logger.error("All migration attempts failed")
                raise
```

---

#### Rollback Strategy

```python
async def safe_upgrade_with_rollback():
    """Upgrade with automatic rollback on failure."""
    runner = MigrationRunner(engine)
    
    # Record current version
    initial_version = await runner.get_current_version()
    logger.info(f"Current version: {initial_version}")
    
    try:
        # Attempt upgrade
        await runner.upgrade_to_head()
        logger.info("✓ Upgrade successful")
        
        # Verify application can start
        # ... your application initialization ...
        
    except Exception as e:
        logger.error(f"Upgrade or startup failed: {e}")
        
        if initial_version:
            logger.info(f"Rolling back to version {initial_version}")
            await runner.downgrade(target=initial_version)
            logger.info("✓ Rollback completed")
        
        raise
```

---

### CI/CD Best Practices

#### Pre-Deployment Migration Check

```yaml
# .github/workflows/pre-deploy.yml
- name: Check migrations
  run: |
    # Check if migrations are needed
    python -m py_accountant.infrastructure.migrations pending > pending.txt
    
    if grep -q "Pending migrations" pending.txt; then
      echo "⚠️  Pending migrations detected"
      cat pending.txt
      echo "migrations_needed=true" >> $GITHUB_OUTPUT
    else
      echo "✓ No pending migrations"
      echo "migrations_needed=false" >> $GITHUB_OUTPUT
    fi
```

---

#### Atomic Deployments

```bash
#!/bin/bash
# deploy.sh - Atomic deployment with migrations

set -e

echo "=== Starting Deployment ==="

# 1. Backup database (PostgreSQL example)
echo "Backing up database..."
pg_dump $DATABASE_URL > backup_$(date +%Y%m%d_%H%M%S).sql

# 2. Run migrations
echo "Running migrations..."
python -m py_accountant.infrastructure.migrations upgrade head

# 3. Verify schema
CURRENT=$(python -m py_accountant.infrastructure.migrations current | grep -oP '\d{4}')
echo "Schema version: $CURRENT"

# 4. Deploy application
echo "Deploying application..."
# ... your deployment commands ...

echo "✓ Deployment complete"
```

---

#### Separate Migration and Deploy Steps

```yaml
# .github/workflows/deploy.yml
jobs:
  migrate:
    name: Run Migrations
    runs-on: ubuntu-latest
    steps:
      - name: Run migrations
        env:
          DATABASE_URL: ${{ secrets.PROD_DATABASE_URL }}
        run: |
          python -m py_accountant.infrastructure.migrations upgrade head
      
      - name: Verify
        run: |
          python -m py_accountant.infrastructure.migrations current
  
  deploy:
    name: Deploy Application
    needs: migrate  # ← Runs only after migrations succeed
    runs-on: ubuntu-latest
    steps:
      - name: Deploy
        run: |
          # Your deployment script
```

---

### Production Considerations

#### Downtime Windows

For **large migrations** that may take time:

1. **Schedule maintenance window**
   ```python
   # Estimate migration time (test in staging first)
   # For large tables (millions of rows), consider:
   # - Breaking into smaller migrations
   # - Using PostgreSQL CONCURRENTLY for indexes
   ```

2. **Notify users**
   ```python
   # Before migration
   await notify_users("Scheduled maintenance in 10 minutes")
   
   # Run migration
   await runner.upgrade_to_head()
   
   # After migration
   await notify_users("Maintenance complete. System is online.")
   ```

3. **Use blue-green deployment** (for zero-downtime)
   ```
   1. Deploy new version to "green" environment
   2. Run migrations on "green" database
   3. Test "green" environment
   4. Switch traffic to "green"
   5. Keep "blue" as fallback
   ```

---

#### Database Backups

**Always backup before migrations**:

```bash
#!/bin/bash
# backup_and_migrate.sh

# PostgreSQL backup
pg_dump $DATABASE_URL > backup_$(date +%Y%m%d_%H%M%S).sql

# SQLite backup
cp mydb.db mydb.db.backup_$(date +%Y%m%d_%H%M%S)

# Run migrations
python -m py_accountant.infrastructure.migrations upgrade head

# Verify
python -m py_accountant.infrastructure.migrations current
```

---

#### Monitoring and Alerting

```python
import time
from py_accountant.infrastructure.migrations import MigrationRunner

async def run_migrations_with_monitoring():
    """Run migrations with timing and alerting."""
    runner = MigrationRunner(engine)
    
    start_time = time.time()
    
    try:
        logger.info("Starting migrations...")
        await runner.upgrade_to_head()
        
        duration = time.time() - start_time
        logger.info(f"✓ Migrations completed in {duration:.2f}s")
        
        # Send success metric
        await send_metric("migration.success", 1)
        await send_metric("migration.duration", duration)
        
    except MigrationError as e:
        duration = time.time() - start_time
        logger.error(f"Migration failed after {duration:.2f}s: {e}")
        
        # Send failure metric and alert
        await send_metric("migration.failure", 1)
        await send_alert(f"Migration failed: {e}")
        
        raise
```

---

#### Lock Mechanisms (PostgreSQL)

Prevent concurrent migrations using advisory locks:

```python
from sqlalchemy import text

async def run_migrations_with_lock():
    """Run migrations with PostgreSQL advisory lock."""
    runner = MigrationRunner(engine)
    
    async with engine.begin() as conn:
        # Try to acquire lock (doesn't block)
        result = await conn.execute(
            text("SELECT pg_try_advisory_lock(12345)")
        )
        lock_acquired = result.scalar()
        
        if not lock_acquired:
            logger.warning("Another migration is in progress")
            raise RuntimeError("Migration already running")
        
        try:
            await runner.upgrade_to_head()
        finally:
            # Release lock
            await conn.execute(text("SELECT pg_advisory_unlock(12345)"))
```

---

### Performance Considerations

#### Analyze Migration Duration

Test migrations in staging environment:

```bash
# Measure migration time
time python -m py_accountant.infrastructure.migrations upgrade head
```

For large databases:
- Migrations with indexes on large tables may take minutes/hours
- Consider `CONCURRENTLY` for PostgreSQL indexes (already used in migrations)
- Test with production-sized data in staging

---

#### Index Creation Strategy

py_accountant migrations already use PostgreSQL `CONCURRENTLY` where possible:

```python
# Example from 0003_add_performance_indexes.py
op.create_index(
    "idx_transaction_lines_account",
    "transaction_lines",
    ["account_id"],
    postgresql_concurrently=True,  # ← Non-blocking
)
```

**No downtime** for index creation on PostgreSQL!

---

### Testing Best Practices

#### Test Migrations in Staging

```bash
# 1. Restore production data to staging
pg_dump production_db > prod_dump.sql
psql staging_db < prod_dump.sql

# 2. Run migrations
DATABASE_URL=staging_url python -m py_accountant.infrastructure.migrations upgrade head

# 3. Verify data integrity
# ... run data validation queries ...

# 4. Test application
# ... run integration tests ...
```

---

#### Test Rollback Procedures

```bash
# 1. Run migration
python -m py_accountant.infrastructure.migrations upgrade head

# 2. Test rollback
python -m py_accountant.infrastructure.migrations downgrade -1

# 3. Verify data still intact
# ... run validation queries ...

# 4. Re-apply migration
python -m py_accountant.infrastructure.migrations upgrade head
```

---

#### Include Migration Tests in CI

```yaml
# .github/workflows/test.yml
- name: Test migrations
  run: |
    # Apply all migrations
    python -m py_accountant.infrastructure.migrations upgrade head
    
    # Run integration tests
    pytest tests/integration/
    
    # Test downgrade
    python -m py_accountant.infrastructure.migrations downgrade -1
    
    # Re-apply
    python -m py_accountant.infrastructure.migrations upgrade head
```

---

### Development Best Practices

#### Don't Modify Existing Migrations

❌ **Never modify** migrations that have been applied in production:
```python
# DON'T DO THIS if migration already applied
def upgrade():
    op.add_column(...)  # ← Don't change existing migrations
```

✅ **Instead**, create a new migration:
```bash
alembic revision -m "add_missing_column"
```

---

#### Keep Migrations Idempotent

Migrations should be safe to run multiple times:

```python
# Good: Check before creating
def upgrade():
    # Check if column exists (Alembic handles this)
    op.add_column('accounts', sa.Column('new_field', sa.String))

# Alembic already makes most operations idempotent
```

---

#### Document Complex Migrations

```python
"""Add performance indexes for transaction queries.

Revision ID: 0003
Revises: 0002
Create Date: 2024-01-15

This migration adds indexes to improve query performance for:
- Transaction line lookups by account (90% faster)
- Journal entry retrieval by timestamp (80% faster)

Expected duration: ~30 seconds for 1M rows
Downtime: None (uses CONCURRENTLY)
"""

def upgrade():
    # ... migration code ...
```

---

## Summary

**Key Best Practices**:
1. ✅ **Always validate schema version** on startup
2. ✅ **Backup before migrations** in production
3. ✅ **Test migrations in staging** first
4. ✅ **Monitor migration duration** and alert on failures
5. ✅ **Separate migration and deploy steps** in CI/CD
6. ✅ **Use advisory locks** to prevent concurrent migrations (PostgreSQL)
7. ✅ **Test rollback procedures** before production deployment
8. ✅ **Never modify existing migrations** already in production

---

## Troubleshooting

### Common Issues

#### Issue 1: KeyError: 'False'

**Symptom**:
```
KeyError: 'False'
  File ".../sqlalchemy/log.py", line 139, in _echo_setter
```

**Cause**:
- `echo` parameter passed as string `'False'` instead of boolean `False`
- Bug in py_accountant < 1.2.0

**Solution**:
✅ **Upgrade to py_accountant ≥ 1.2.0** (fixed in Wave 7)

```bash
pip install --upgrade py-accountant
```

**Workaround** (if you can't upgrade):
```python
# Explicitly pass boolean
runner = MigrationRunner(engine, echo=False)  # ← Not 'False'
```

**Fixed in**: py_accountant 1.2.0

---

#### Issue 2: "Async driver not supported for Alembic"

**Symptom**:
```
RuntimeError: Async driver asyncpg is not supported for Alembic migrations
```

**Cause**:
- `DATABASE_URL` environment variable contains async driver (`asyncpg`, `aiosqlite`)
- Alembic requires sync drivers

**Solution**:

**Option 1**: Use sync URL in environment variable
```bash
# ❌ Wrong
export DATABASE_URL="postgresql+asyncpg://user:pass@localhost/db"

# ✅ Correct
export DATABASE_URL="postgresql+psycopg://user:pass@localhost/db"
```

**Option 2**: Let MigrationRunner convert automatically (recommended)
```python
# Pass async engine - MigrationRunner converts URL automatically
engine = create_async_engine("postgresql+asyncpg://localhost/db")
runner = MigrationRunner(engine)  # ← Auto-converts to psycopg
await runner.upgrade_to_head()
```

**Note**: MigrationRunner automatically converts:
- `postgresql+asyncpg://` → `postgresql+psycopg://`
- `sqlite+aiosqlite://` → `sqlite+pysqlite://`

**Fixed in**: py_accountant 1.2.0 (automatic conversion)

---

#### Issue 3: Migrations Not Executing

**Symptom**:
- CLI reports success: `"✓ Upgraded to head"`
- But tables are not created in database
- No errors shown

**Cause**:
- `env.py` execution model issue
- Bug in py_accountant < 1.2.0

**Solution**:
✅ **Upgrade to py_accountant ≥ 1.2.0** (fixed in Wave 7)

```bash
pip install --upgrade py-accountant
```

**Verification**:
```bash
# Check if tables were actually created
python -c "
from sqlalchemy import create_engine, inspect
engine = create_engine('your_database_url')
inspector = inspect(engine)
print('Tables:', inspector.get_table_names())
"
```

**Fixed in**: py_accountant 1.2.0

---

#### Issue 4: VersionMismatchError

**Symptom**:
```
VersionMismatchError: Schema version mismatch: current=0005, expected=0008
```

**Cause**:
- Code updated to newer version, but database migrations not applied
- Common after `git pull` or package upgrade

**Solution**:

**Option 1**: Run migrations manually
```bash
python -m py_accountant.infrastructure.migrations upgrade head
```

**Option 2**: Auto-upgrade on startup (use with caution)
```python
from py_accountant import __version_schema__
from py_accountant.infrastructure.migrations import MigrationRunner, VersionMismatchError

try:
    await runner.validate_schema_version(__version_schema__)
except VersionMismatchError:
    logger.warning("Schema outdated, upgrading...")
    await runner.upgrade_to_head()
```

**Prevention**:
```python
# Add validation to application startup
async def startup():
    runner = MigrationRunner(engine)
    current = await runner.get_current_version()
    
    if current != __version_schema__:
        raise RuntimeError(
            f"Schema version mismatch. "
            f"Run: python -m py_accountant.infrastructure.migrations upgrade head"
        )
```

---

#### Issue 5: "Database not initialized"

**Symptom**:
```
sqlalchemy.exc.ProgrammingError: (psycopg.errors.UndefinedTable) 
relation "accounts" does not exist
```

**Cause**:
- No migrations have been applied yet
- Database is empty

**Solution**:
```bash
# Run migrations to create tables
python -m py_accountant.infrastructure.migrations upgrade head
```

**Prevention**:
- Add migration check to startup
- Use Docker entrypoint to run migrations automatically
- Document initialization steps in README

---

#### Issue 6: Import Errors

**Symptom**:
```
ModuleNotFoundError: No module named 'py_accountant.infrastructure.migrations'
```

**Cause 1**: Incorrect import path
```python
# ❌ Wrong
from py_accountant.migrations import MigrationRunner

# ✅ Correct
from py_accountant.infrastructure.migrations import MigrationRunner
```

**Cause 2**: Package not installed
```bash
pip install py-accountant
```

**Cause 3**: Virtual environment not activated
```bash
source venv/bin/activate  # or: poetry shell
```

---

#### Issue 7: "context.config has no attribute..."

**Symptom**:
```
AttributeError: 'Config' object has no attribute 'attributes'
```

**Cause**:
- Bug in py_accountant < 1.2.0 when using CLI

**Solution**:
✅ **Upgrade to py_accountant ≥ 1.2.0** (fixed in Wave 7)

**Fixed in**: py_accountant 1.2.0

---

#### Issue 8: PostgreSQL Lock Timeout

**Symptom**:
```
psycopg.errors.LockNotAvailable: could not obtain lock on relation "accounts"
```

**Cause**:
- Table locked by another transaction
- Long-running query holding lock

**Solution**:

**Option 1**: Wait and retry
```python
import asyncio

for attempt in range(3):
    try:
        await runner.upgrade_to_head()
        break
    except MigrationError as e:
        if "could not obtain lock" in str(e):
            logger.warning(f"Lock timeout, retrying ({attempt + 1}/3)...")
            await asyncio.sleep(5)
        else:
            raise
```

**Option 2**: Kill blocking queries
```sql
-- Find blocking queries
SELECT pid, query FROM pg_stat_activity 
WHERE state = 'active' AND query NOT ILIKE '%pg_stat_activity%';

-- Kill blocking query (careful!)
SELECT pg_terminate_backend(pid);
```

**Prevention**:
- Run migrations during maintenance window
- Ensure no long-running queries during migration

---

### Debug Tips

#### Enable SQL Echo

```python
# See all SQL statements
runner = MigrationRunner(engine, echo=True)
await runner.upgrade_to_head()
```

```bash
# CLI with echo
python -m py_accountant.infrastructure.migrations upgrade head --echo
```

---

#### Check DATABASE_URL

```python
import os
print(f"DATABASE_URL: {os.getenv('DATABASE_URL')}")

# Verify connection
from sqlalchemy import create_engine
engine = create_engine(os.getenv("DATABASE_URL"))
with engine.connect() as conn:
    result = conn.execute("SELECT 1")
    print(f"Connection OK: {result.scalar()}")
```

---

#### Verify Sync/Async Driver

```python
from sqlalchemy import create_engine

url = "postgresql+asyncpg://localhost/db"  # ❌ Async driver
engine = create_engine(url)  # Will fail

url_sync = "postgresql+psycopg://localhost/db"  # ✅ Sync driver
engine = create_engine(url_sync)  # OK
```

---

#### Check Alembic Version Table

```sql
-- PostgreSQL
SELECT * FROM alembic_version;

-- Should show current revision, e.g., '0008'
```

```python
# Python
from sqlalchemy import text

async with engine.begin() as conn:
    result = await conn.execute(text("SELECT version_num FROM alembic_version"))
    version = result.scalar()
    print(f"Current version: {version}")
```

---

#### Manual SQL Inspection

```bash
# PostgreSQL
psql $DATABASE_URL -c "\dt"  # List tables
psql $DATABASE_URL -c "\d accounts"  # Describe table

# SQLite
sqlite3 mydb.db ".tables"  # List tables
sqlite3 mydb.db ".schema accounts"  # Show schema
```

---

#### Check Migration Files

```bash
# List available migrations
ls src/py_accountant/infrastructure/migrations/versions/

# Expected files:
# 0001_initial.py
# 0002_add_is_base_currency.py
# ...
# 0008_add_account_aggregates.py
```

---

### Getting Help

If you're still stuck:

1. **Check documentation**:
   - [Integration Guide](INTEGRATION_GUIDE.md)
   - [Architecture Overview](ARCHITECTURE_OVERVIEW.md)
   - [API Reference](API_REFERENCE.md)

2. **Enable debug logging**:
   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)
   ```

3. **Create GitHub Issue**:
   - Repository: [py_accountant on GitHub](https://github.com/your-repo/py_accountant)
   - Include:
     - Python version
     - py_accountant version
     - Database (PostgreSQL/SQLite)
     - Full error message
     - Minimal reproduction code

4. **Community**:
   - GitHub Discussions
   - Stack Overflow (tag: `py-accountant`)

---

## Issue Summary Table

| Issue | Symptom | Cause | Solution | Fixed In |
|-------|---------|-------|----------|----------|
| KeyError: 'False' | KeyError in sqlalchemy/log.py | echo as string | Upgrade to 1.2.0 | 1.2.0 |
| Async driver error | RuntimeError: asyncpg not supported | Async URL | Use sync URL or MigrationRunner | 1.2.0 |
| Migrations not executing | Success but no tables | env.py bug | Upgrade to 1.2.0 | 1.2.0 |
| Version mismatch | VersionMismatchError | Code updated, DB not | Run migrations | N/A |
| Database not initialized | UndefinedTable error | No migrations applied | Run `upgrade head` | N/A |
| Import errors | ModuleNotFoundError | Wrong import path | Fix import | N/A |
| context.config error | AttributeError | CLI bug | Upgrade to 1.2.0 | 1.2.0 |
| Lock timeout | LockNotAvailable | Table locked | Wait and retry | N/A |

---

## Advanced Topics

### Custom Migration Templates

Customize the migration template file.

**Default template**: `src/py_accountant/infrastructure/migrations/script.py.mako`

**To customize**:

1. Copy default template:
   ```bash
   cp venv/lib/python3.11/site-packages/py_accountant/infrastructure/migrations/script.py.mako \
      custom_script.py.mako
   ```

2. Modify template:
   ```mako
   ## custom_script.py.mako
   """${message}
   
   Custom template with additional metadata.
   
   Revision ID: ${up_revision}
   Author: ${author}
   Date: ${create_date}
   """
   
   # ... rest of template
   ```

3. Configure Alembic to use custom template:
   ```ini
   # alembic.ini
   [alembic]
   script_location = migrations
   file_template = %%(year)d%%(month).2d%%(day).2d_%%(rev)s_%%(slug)s
   script_template = custom_script.py.mako
   ```

**Note**: py_accountant uses a fixed naming scheme for bundled migrations. Custom templates are for your own migrations only.

---

### Multi-Schema Support (PostgreSQL)

Deploy py_accountant tables to a specific PostgreSQL schema.

#### Using Alembic Integration

```python
# alembic/env.py

from py_accountant.infrastructure.migrations import include_in_alembic

def run_migrations_online():
    # ...
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
    )
    
    # Deploy py_accountant tables to "accounting" schema
    include_in_alembic(context, schema="accounting")
    
    with context.begin_transaction():
        context.run_migrations()
```

#### Manual Schema Creation

```sql
-- Create schema first
CREATE SCHEMA IF NOT EXISTS accounting;

-- Then run migrations
-- Tables will be created as: accounting.accounts, accounting.journals, etc.
```

**Note**: MigrationRunner doesn't directly support schema parameter (use Alembic integration).

---

### Programmatic Configuration

Customize Alembic configuration programmatically.

```python
from alembic.config import Config
from py_accountant.infrastructure.migrations import MigrationRunner

# Create custom Alembic config
alembic_cfg = Config()
alembic_cfg.set_main_option("script_location", "/custom/path/migrations")
alembic_cfg.set_main_option("sqlalchemy.url", "postgresql://...")

# Write config to temp file
import tempfile
with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as f:
    alembic_cfg.config_file_name = f.name
    # Write config...

# Use custom config
runner = MigrationRunner(engine, alembic_config_path=f.name)
await runner.upgrade_to_head()
```

**Use case**: Dynamic configuration in multi-tenant applications.

---

### Custom Revision Naming

py_accountant uses 4-digit sequential naming: `0001`, `0002`, etc.

For **your own migrations** (if extending py_accountant):

```bash
# Create migration with custom name
alembic revision -m "add_custom_feature"

# Generates: YYYYMMDD_<rev>_add_custom_feature.py
```

---

### Migration Hooks (Future Feature)

**Not yet implemented**, but planned for future versions:

```python
# Future API (example)
runner = MigrationRunner(engine)

@runner.before_upgrade
async def backup_database():
    """Run before each upgrade."""
    await create_backup()

@runner.after_upgrade
async def verify_data():
    """Run after each upgrade."""
    await validate_data_integrity()

await runner.upgrade_to_head()  # Runs hooks automatically
```

**Current workaround**:
```python
async def upgrade_with_hooks():
    # Manual hook implementation
    await backup_database()
    
    try:
        await runner.upgrade_to_head()
    finally:
        await verify_data()
```

---

### Dry Run Mode (Future Feature)

**Not yet implemented**, but can be simulated:

```python
# Future API (example)
runner = MigrationRunner(engine, dry_run=True)
sql_statements = await runner.upgrade_to_head()  # Returns SQL, doesn't execute

# Current workaround: Use echo=True
runner = MigrationRunner(engine, echo=True)
await runner.upgrade_to_head()  # Prints SQL statements
```

---

### Offline Migration Generation

Generate SQL scripts for manual execution (without database connection).

**Use Alembic directly**:

```bash
# Generate SQL for upgrade
alembic upgrade head --sql > migrations.sql

# Review and execute manually
psql $DATABASE_URL -f migrations.sql
```

**Use case**: 
- Restricted database access (DBA must run migrations)
- Audit requirements (manual review before execution)
- Production safety (generate → review → apply)

---

### Integration with Other ORMs

py_accountant uses SQLAlchemy internally, but migrations can coexist with other ORMs.

#### Django

```python
# Django settings.py
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'mydb',
        # ... other settings
    }
}

# Run py_accountant migrations separately
# (Django migrations and py_accountant migrations are independent)
```

#### Tortoise ORM

```python
# Use MigrationRunner before Tortoise initialization
await runner.upgrade_to_head()

# Then initialize Tortoise
from tortoise import Tortoise
await Tortoise.init(db_url="postgresql://...", modules={...})
```

**Key point**: py_accountant migrations manage py_accountant tables only. Your application can use any ORM for its own tables.

---

## Advanced Topics Summary

- ✅ **Custom templates** - For your own migrations
- ✅ **Multi-schema** - Deploy to specific PostgreSQL schema
- ✅ **Programmatic config** - Dynamic Alembic configuration
- ⏳ **Hooks** - Future feature (use manual workaround)
- ⏳ **Dry run** - Future feature (use echo=True)
- ✅ **Offline SQL** - Use Alembic's `--sql` flag
- ✅ **Other ORMs** - py_accountant migrations are independent

---

## See Also

### py_accountant Documentation

- [Integration Guide](INTEGRATION_GUIDE.md) - How to integrate py_accountant into your application
- [API Reference](API_REFERENCE.md) - Complete API documentation for accounting operations
- [Architecture Overview](ARCHITECTURE_OVERVIEW.md) - System design and component relationships
- [Performance Guide](PERFORMANCE.md) - Optimization tips and benchmarks
- [Configuration Reference](CONFIG_REFERENCE.md) - Configuration options

### Examples

- [FastAPI Example](../examples/fastapi_basic/) - Complete FastAPI integration
- [CLI Example](../examples/cli_basic/) - Command-line application
- [Telegram Bot Example](../examples/telegram_bot/) - aiogram integration
- [Alembic Integration Example](../examples/alembic_integration/) - Existing Alembic project

### External Resources

- [Alembic Documentation](https://alembic.sqlalchemy.org/en/latest/) - Official Alembic docs
  - [Tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html) - Getting started with Alembic
  - [Operations Reference](https://alembic.sqlalchemy.org/en/latest/ops.html) - Available migration operations
- [SQLAlchemy Async](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html) - Async SQLAlchemy guide
- [PostgreSQL Documentation](https://www.postgresql.org/docs/) - PostgreSQL reference
- [SQLite Documentation](https://www.sqlite.org/docs.html) - SQLite reference

### Related Topics

- [Double-Entry Accounting](ACCOUNTING_CHEATSHEET.md) - Accounting concepts primer
- [FX Handling](FX_AUDIT.md) - Multi-currency support
- [Trading Windows](TRADING_WINDOWS.md) - Time-based exchange rate management

### Community

- [GitHub Repository](https://github.com/your-org/py_accountant) - Source code and issues
- [GitHub Discussions](https://github.com/your-org/py_accountant/discussions) - Community Q&A
- [Changelog](CHANGELOG.md) - Version history and release notes

### Support

- **Bug reports**: [GitHub Issues](https://github.com/your-org/py_accountant/issues)
- **Feature requests**: [GitHub Discussions](https://github.com/your-org/py_accountant/discussions/categories/ideas)
- **Security issues**: security@your-org.com

---

## Appendix

### A. Migration Files Reference

Complete list of py_accountant migrations (as of version 1.2.0):

| Revision | File | Description | Key Changes |
|----------|------|-------------|-------------|
| 0001 | `0001_initial.py` | Initial schema | `accounts`, `currencies`, `journals`, `journal_entries`, `transaction_lines` tables |
| 0002 | `0002_add_is_base_currency.py` | Base currency flag | `currencies.is_base_currency` column |
| 0003 | `0003_add_performance_indexes.py` | Query optimization | Indexes on `account_id`, `created_at`, `journal_id` |
| 0004 | `0004_add_exchange_rate_events.py` | FX event tracking | `exchange_rate_events` table |
| 0005 | `0005_exchange_rate_events_archive.py` | FX event archival | `exchange_rate_events_archive` table |
| 0006 | `0006_add_journal_idempotency_key.py` | Idempotency | `journals.idempotency_key` column (unique) |
| 0007 | `0007_drop_balances_table.py` | Remove denormalization | Drop `balances` table (use aggregates instead) |
| 0008 | `0008_add_account_aggregates.py` | Account aggregation | `account_aggregates` table for efficient balance queries |

**Latest version**: `0008`

---

### B. Database Schema (After All Migrations)

#### Core Tables

**`accounts`**
- Stores chart of accounts (assets, liabilities, equity, revenue, expenses)
- Columns: `id`, `code`, `name`, `type`, `currency_code`, `parent_id`, `is_active`, `created_at`, `updated_at`
- Indexes: `code` (unique), `type`, `currency_code`, `parent_id`

**`currencies`**
- Supported currencies
- Columns: `code` (PK), `name`, `symbol`, `decimal_places`, `is_base_currency`, `created_at`
- Constraints: Only one base currency allowed

**`journals`**
- Journal entries (transactions)
- Columns: `id`, `description`, `entry_date`, `created_at`, `idempotency_key`
- Indexes: `entry_date`, `idempotency_key` (unique), `created_at`

**`journal_entries`** (⚠️ Deprecated, use `journals`)
- Legacy table, may be removed in future versions

**`transaction_lines`**
- Detailed ledger entries (debits and credits)
- Columns: `id`, `journal_id`, `account_id`, `amount`, `currency_code`, `description`, `created_at`
- Indexes: `journal_id`, `account_id`, `created_at`
- Constraints: Foreign keys to `journals` and `accounts`

#### Aggregation Tables

**`account_aggregates`**
- Pre-computed account balances (performance optimization)
- Columns: `id`, `account_id`, `balance`, `currency_code`, `as_of_date`, `created_at`, `updated_at`
- Indexes: `account_id`, `as_of_date`
- Use case: Fast balance queries without summing all transaction lines

#### FX Tables

**`exchange_rate_events`**
- Real-time exchange rate updates
- Columns: `id`, `from_currency`, `to_currency`, `rate`, `timestamp`, `source`, `created_at`
- Indexes: `timestamp`, `from_currency`, `to_currency`

**`exchange_rate_events_archive`**
- Historical exchange rate data (archival)
- Same schema as `exchange_rate_events`
- Use case: Move old rates out of hot table for performance

#### System Tables

**`alembic_version`**
- Alembic migration tracking
- Columns: `version_num` (PK)
- Contains current migration revision (e.g., `'0008'`)

---

### C. Version History

**py_accountant Migration API versions**:

| Version | Date | Changes |
|---------|------|---------|
| 1.2.0 | Nov 2025 | Initial Migration API release (Waves 1-8) |
|       |          | - MigrationRunner programmatic API |
|       |          | - CLI commands (upgrade, downgrade, current, pending, history) |
|       |          | - Alembic integration (include_in_alembic) |
|       |          | - 8 database migrations (0001-0008) |
|       |          | - Bug fixes: KeyError, async driver, context.config |
| 1.3.0 | TBD | Planned: Migration hooks, dry run mode |

**Schema versions**:

| Schema Version | py_accountant Version | Description |
|----------------|----------------------|-------------|
| 0008 | 1.2.0+ | Current (account aggregates) |
| 0007 | 1.2.0 | Dropped balances table |
| 0006 | 1.2.0 | Idempotency keys |
| 0001-0005 | 1.2.0 | Initial schema evolution |

**Check your schema version**:
```python
from py_accountant import __version_schema__
print(__version_schema__)  # e.g., '0008'
```

---

### D. Terminology

| Term | Definition |
|------|------------|
| **Migration** | A database schema change (adding tables, columns, indexes, etc.) |
| **Revision** | A specific migration version (e.g., `0008`) |
| **Head** | The latest migration revision |
| **Base** | No migrations applied (empty database) |
| **Upgrade** | Apply migrations to move forward (e.g., 0005 → 0008) |
| **Downgrade** | Revert migrations to move backward (e.g., 0008 → 0005) |
| **Pending** | Migrations not yet applied |
| **Alembic** | Database migration tool used by py_accountant |
| **Schema version** | Current migration revision in database |
| **Idempotent** | Safe to run multiple times (produces same result) |

---

### E. Environment Variable Reference

| Variable | Description | Example | Required |
|----------|-------------|---------|----------|
| `DATABASE_URL` | Database connection URL | `postgresql+psycopg://user:pass@localhost/db` | Yes (for CLI) |
| `PYACC__DATABASE_URL` | py_accountant specific URL (higher priority) | Same format | No |
| `ALEMBIC_CONFIG` | Path to custom alembic.ini | `/path/to/alembic.ini` | No |

**URL formats**:
- PostgreSQL: `postgresql+psycopg://user:pass@host:port/database`
- SQLite: `sqlite:///path/to/file.db` (absolute path)
- SQLite: `sqlite:///./relative/path/file.db` (relative path)

**Note**: Use sync drivers (`psycopg`, `pysqlite`), not async (`asyncpg`, `aiosqlite`) for CLI.

---

### F. Exit Codes (CLI)

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Error (migration failed, invalid arguments, etc.) |

**Example usage in scripts**:
```bash
#!/bin/bash
python -m py_accountant.infrastructure.migrations upgrade head
if [ $? -ne 0 ]; then
  echo "Migration failed!"
  exit 1
fi
```

---

### G. Performance Benchmarks

Typical migration times (tested on PostgreSQL 15, 1M transaction_lines):

| Migration | Duration | Notes |
|-----------|----------|-------|
| 0001 (initial) | ~2s | Creates base tables |
| 0003 (indexes) | ~30s | Index creation (CONCURRENTLY) |
| 0008 (aggregates) | ~5s | Creates aggregate table |
| **Full upgrade (0001 → 0008)** | **~45s** | Complete schema initialization |

**Notes**:
- Times vary based on hardware, database size, and load
- Index creation uses `CONCURRENTLY` (non-blocking on PostgreSQL)
- SQLite migrations are typically faster (<5s total)

---

## End of Documentation

**Версия**: 1.0.0  
**Дата обновления**: 27 ноября 2025  
**Совместимость**: py_accountant >= 1.2.0

For updates, see [CHANGELOG.md](CHANGELOG.md).


