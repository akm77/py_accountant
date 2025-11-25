```markdown
```bash
# 1) Миграции
poetry run alembic upgrade head
# 2) Базовые операции выполняются через core (`py_accountant.*`, см. примеры ниже)
```

## Runtime vs Migration Database URLs (dual‑URL)

Для безопасного использования SQLAlchemy в проекте применяются два URL:

| Назначение | Переменная | Пример | Допустимые драйверы |
|------------|-----------|--------|---------------------|
| Миграции (Alembic) | `DATABASE_URL` / `PYACC__DATABASE_URL` | `postgresql+psycopg://user:pass@host:5432/db` | `postgresql`, `postgresql+psycopg`, `sqlite`, `sqlite+pysqlite` |
| Runtime (async) | `DATABASE_URL_ASYNC` / `PYACC__DATABASE_URL_ASYNC` | `postgresql+asyncpg://user:pass@host:5432/db` | `postgresql+asyncpg`, `sqlite+aiosqlite` |

Правила:
- Alembic читает только `DATABASE_URL` (или fallback из `alembic.ini`); async‑драйверы там запрещены.
- Инфраструктурный слой (`py_accountant.infrastructure.persistence.sqlalchemy.*` и `AsyncSqlAlchemyUnitOfWork`) использует `DATABASE_URL_ASYNC` (или `PYACC__DATABASE_URL_ASYNC`). При его отсутствии допускается нормализация sync URL (любого из ключей) в async.
- В CI шаг миграций использует sync URL; рантайм — async.
- См. также `docs/RUNNING_MIGRATIONS.md`.

Пример `.env`:
```
TELEGRAM_BOT_TOKEN=bot-token
BOT__SOME_SETTING=value
PYACC__DATABASE_URL=postgresql+psycopg://acc:pass@localhost:5432/ledger
PYACC__DATABASE_URL_ASYNC=postgresql+asyncpg://acc:pass@localhost:5432/ledger
PYACC__LOG_LEVEL=INFO
PYACC__LOGGING_ENABLED=true
```

Необязательные параметры logging/TTL также поддерживают двойное имя (`LOG_LEVEL` и `PYACC__LOG_LEVEL`).

Workflow:
```bash
poetry run alembic upgrade head   # читает DATABASE_URL или PYACC__DATABASE_URL
PYTHONPATH=src poetry run python -m examples.telegram_bot.app  # runtime async URL
```

### Отключение встроенного логгера SDK
- В инфраструктурном слое задайте `LOGGING_ENABLED=false` (или `PYACC__LOGGING_ENABLED=false`), чтобы SDK пропустил настройку structlog и позволил хост-приложению использовать собственный logger/handlers.
- Поведение UoW и use case'ов не меняется: `app.logger` остаётся доступным, но не имеет обработчиков, пока вы не настроите их самостоятельно.

## Использование как библиотеки (core-only)

Интеграция осуществляется напрямую через use case'ы и порты модуля `py_accountant.application`, без отдельного SDK‑обёртки. Во внешних проектах используйте только импорты вида `py_accountant.*`.

### 1. Зависимость

```bash
poetry add git+https://github.com/akm77/py_accountant.git
# или
pip install "git+https://github.com/akm77/py_accountant.git"
```

### 2. Реализация собственного UoW

```python
from collections.abc import Callable
from py_accountant.application.ports import UnitOfWork as UnitOfWorkProtocol


class MyUnitOfWork(UnitOfWorkProtocol):
    def __enter__(self) -> "MyUnitOfWork":
        # открыть сессию/подключение, инициализировать репозитории
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        # commit/rollback и закрыть сессию
        ...

    # свойства/репозитории, которые ожидают use case'ы


def make_uow_factory(url: str) -> Callable[[], UnitOfWorkProtocol]:
    def factory() -> UnitOfWorkProtocol:
        return MyUnitOfWork(url)

    return factory
```

### 3. Вызов use case'ов ledger

```python
from py_accountant.application.use_cases.ledger import PostTransaction, GetBalance


def post_deposit(uow_factory, clock, account: str, amount, currency: str, meta: dict):
    lines = [
        # Заполните EntryLineDTO по своим правилам маппинга
    ]
    with uow_factory() as uow:
        use_case = PostTransaction(uow, clock)
        return use_case(lines=lines, memo="Deposit", meta=meta)


def get_balance(uow_factory, clock, account: str):
    with uow_factory() as uow:
        use_case = GetBalance(uow, clock)
        return use_case(account_full_name=account)
```

### 4. Где искать контракты

- Порты: `py_accountant.application.ports`.
- Use case'ы (sync): `py_accountant.application.use_cases.*`.
- Use case'ы (async): `py_accountant.application.use_cases_async.*`.

Документ согласован с кодом: `src/py_accountant/application/use_cases/ledger.py`,
`src/py_accountant/application/use_cases_async/*`, `src/py_accountant/application/ports.py`.

---

## Детальные примеры интеграции

Для подробных пошаговых руководств по интеграции в конкретные фреймворки см.:

- **[INTEGRATION_GUIDE_AIOGRAM.md](INTEGRATION_GUIDE_AIOGRAM.md)** — Полное руководство по интеграции в Telegram Bot на aiogram 3.x
  - Структура проекта и зависимости
  - UnitOfWork и Clock адаптеры
  - Маппинг команд на use cases
  - Dependency Injection через middlewares
  - Error handling и логирование
  - CI/CD, Docker, миграции в production
  - Тестирование (unit, integration, e2e)
  - Production checklist с мониторингом и безопасностью

---

## Configuration Deep Dive

### Dual-URL Architecture

py_accountant использует **dual-URL architecture** для разделения миграций и runtime операций:

1. **DATABASE_URL** (sync) — для Alembic миграций
   - Использует sync драйверы: `psycopg` (PostgreSQL), `pysqlite` (SQLite)
   - Alembic требует sync connection
   - Читается из `alembic/env.py`

2. **DATABASE_URL_ASYNC** (async) — для runtime операций
   - Использует async драйверы: `asyncpg` (PostgreSQL), `aiosqlite` (SQLite)
   - AsyncUnitOfWork требует async connection
   - Читается из `infrastructure.persistence.sqlalchemy.async_engine`

**Почему два URL?**
- Alembic не поддерживает async операции
- Runtime использует async для лучшей конкурентности
- Позволяет использовать разные параметры подключения (pooling, timeouts)

**Migration Flow**:
```
DATABASE_URL (sync) → Alembic → Schema changes → Database
                                                      ↓
DATABASE_URL_ASYNC (async) → AsyncUnitOfWork → Runtime operations
```

**Пример настройки**:
```python
# alembic/env.py (sync)
from os import getenv
DATABASE_URL = getenv("DATABASE_URL")
# Использует psycopg driver

# infrastructure/persistence/sqlalchemy/async_engine.py (async)
from os import getenv
DATABASE_URL_ASYNC = getenv("DATABASE_URL_ASYNC")
# Использует asyncpg driver
```

### Environment-Specific Configuration

#### Development (.env.dev)
```bash
DATABASE_URL=sqlite+pysqlite:///./dev.db
DATABASE_URL_ASYNC=sqlite+aiosqlite:///./dev.db
LOG_LEVEL=DEBUG
LOGGING_ENABLED=true
JSON_LOGS=false
FX_TTL_MODE=none
```

**Преимущества**: Простая настройка, нет внешних зависимостей  
**Недостатки**: Не для production, ограниченная конкурентность

#### Staging (.env.staging)
```bash
DATABASE_URL=postgresql+psycopg://user:pass@staging-db:5432/ledger
DATABASE_URL_ASYNC=postgresql+asyncpg://user:pass@staging-db:5432/ledger
LOG_LEVEL=INFO
JSON_LOGS=true
LOG_FILE=/var/log/py_accountant_staging.json
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20
FX_TTL_MODE=archive
FX_TTL_RETENTION_DAYS=30
FX_TTL_DRY_RUN=true
```

**Преимущества**: Отражает production, позволяет тестирование  
**Недостатки**: Требует PostgreSQL instance

#### Production (.env.prod или Secrets Manager)
```bash
DATABASE_URL=postgresql+psycopg://user:${DB_PASSWORD}@prod-db:5432/ledger
DATABASE_URL_ASYNC=postgresql+asyncpg://user:${DB_PASSWORD}@prod-db:5432/ledger
LOG_LEVEL=WARNING
LOGGING_ENABLED=false
JSON_LOGS=true
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=40
DB_POOL_RECYCLE_SEC=3600
FX_TTL_MODE=archive
FX_TTL_RETENTION_DAYS=90
FX_TTL_BATCH_SIZE=1000
```

**Best Practices**:
- Используйте secrets manager (не .env файл)
- Отключите internal logging (используйте внешнюю систему)
- Настройте connection pooling
- Включите structured logging (JSON)

### Connection Pooling Strategy

**Default Pool Settings**:
```python
DB_POOL_SIZE=5        # Core connections
DB_MAX_OVERFLOW=10    # Additional connections under load
DB_POOL_TIMEOUT=30    # Wait time before error
DB_POOL_RECYCLE_SEC=1800  # Recycle stale connections (30 min)
```

**Sizing Guidelines**:
```
pool_size = concurrent_requests * avg_request_duration

Пример:
- 100 req/sec
- 0.05 sec avg duration
- pool_size = 100 * 0.05 = 5 connections
```

**Load Testing**:
```bash
# Test with different pool sizes
for size in 5 10 20; do
  export DB_POOL_SIZE=$size
  poetry run locust -f tests/load/test_ledger.py --users 100 --spawn-rate 10
done
```

### FX Audit TTL Configuration

**Use Case**: Автоматическая очистка старых exchange rate events.

**Modes**:
1. **none** — Только ручная очистка
2. **delete** — Постоянное удаление
3. **archive** — Архивация в отдельную таблицу, затем удаление

**Configuration**:
```bash
FX_TTL_MODE=archive
FX_TTL_RETENTION_DAYS=90
FX_TTL_BATCH_SIZE=1000
FX_TTL_DRY_RUN=false
```

**Worker Implementation**:
```python
import asyncio
from datetime import UTC, datetime
from py_accountant.application.use_cases_async.fx_audit_ttl import (
    AsyncPlanFxAuditTTL,
    AsyncExecuteFxAuditTTL,
)
from py_accountant.infrastructure.persistence.sqlalchemy.uow import AsyncSqlAlchemyUnitOfWork
from py_accountant.infrastructure.persistence.inmemory.clock import SystemClock

async def fx_ttl_worker(session_factory):
    """Background worker for FX TTL."""
    uow = AsyncSqlAlchemyUnitOfWork(session_factory)
    clock = SystemClock()
    
    plan_ttl = AsyncPlanFxAuditTTL(uow=uow, clock=clock)
    execute_ttl = AsyncExecuteFxAuditTTL(uow=uow, clock=clock)
    
    while True:
        async with uow:
            # Plan TTL
            plan = await plan_ttl(
                retention_days=90,
                batch_size=1000,
                mode="archive",
                dry_run=False
            )
            
            # Execute TTL
            result = await execute_ttl(plan=plan)
            await uow.commit()
            
            print(f"TTL: archived={result.archived_count}, deleted={result.deleted_count}")
        
        # Sleep until next run
        await asyncio.sleep(86400)  # 24 hours

# In main.py
asyncio.create_task(fx_ttl_worker(session_factory))
```

### Secrets Management

#### AWS Secrets Manager
```python
import boto3
import json
import os

def load_secrets():
    client = boto3.client('secretsmanager', region_name='us-east-1')
    response = client.get_secret_value(SecretId='py_accountant/prod')
    secrets = json.loads(response['SecretString'])
    
    os.environ['DATABASE_URL'] = secrets['database_url']
    os.environ['DATABASE_URL_ASYNC'] = secrets['database_url_async']

# Call before initializing UoW
load_secrets()
```

#### Kubernetes Secrets
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: py-accountant-secrets
type: Opaque
stringData:
  DATABASE_URL: postgresql+psycopg://user:pass@db:5432/ledger
  DATABASE_URL_ASYNC: postgresql+asyncpg://user:pass@db:5432/ledger
```

```yaml
# deployment.yaml
env:
  - name: DATABASE_URL
    valueFrom:
      secretKeyRef:
        name: py-accountant-secrets
        key: DATABASE_URL
  - name: DATABASE_URL_ASYNC
    valueFrom:
      secretKeyRef:
        name: py-accountant-secrets
        key: DATABASE_URL_ASYNC
```

#### HashiCorp Vault
```python
import hvac
import os

def load_from_vault():
    client = hvac.Client(url='https://vault.example.com')
    client.auth.approle.login(role_id=ROLE_ID, secret_id=SECRET_ID)
    
    secrets = client.secrets.kv.v2.read_secret_version(path='py_accountant/prod')
    data = secrets['data']['data']
    
    os.environ['DATABASE_URL'] = data['database_url']
    os.environ['DATABASE_URL_ASYNC'] = data['database_url_async']

load_from_vault()
```

### Configuration Validation

Используйте validation script перед деплоем:

```bash
python tools/validate_config.py
```

Expected output:
```
✅ Valid database URL: postgresql://localhost
✅ Valid async database URL: postgresql+asyncpg://localhost
✅ LOG_LEVEL is valid: INFO
✅ FX_TTL_MODE is valid: archive

✅ Configuration validation passed!
```

**См. также**:
- [CONFIG_REFERENCE.md](CONFIG_REFERENCE.md) — Полный справочник переменных окружения
- [FX_AUDIT.md](FX_AUDIT.md) — FX audit TTL детали
- [RUNNING_MIGRATIONS.md](RUNNING_MIGRATIONS.md) — Alembic migrations

