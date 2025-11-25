# Configuration Reference

> **Версия**: 1.1.0-S5  
> **Дата обновления**: 2025-11-25  
> **Статус**: Async-first architecture

## Введение

Этот документ описывает все переменные окружения для настройки py_accountant.

**Ключевые принципы**:
- Dual-URL setup: DATABASE_URL (sync, Alembic) + DATABASE_URL_ASYNC (async, runtime)
- Префикс PYACC__ для namespace separation
- Environment-specific overrides (.env.dev, .env.prod)
- Secret management через external systems (Vault, AWS Secrets Manager)

---

## Quick Start

### Minimal Configuration (.env)

```bash
# Database (required)
DATABASE_URL=sqlite+pysqlite:///./dev.db
DATABASE_URL_ASYNC=sqlite+aiosqlite:///./dev.db

# Logging (optional, defaults provided)
LOG_LEVEL=INFO
LOGGING_ENABLED=true
```

### Production Configuration (.env.prod)

```bash
# PostgreSQL with connection pooling
DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/ledger
DATABASE_URL_ASYNC=postgresql+asyncpg://user:pass@localhost:5432/ledger

# Advanced settings
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=40
DB_POOL_TIMEOUT=30
DB_POOL_RECYCLE_SEC=3600

# Logging
LOG_LEVEL=WARNING
JSON_LOGS=true
LOG_FILE=/var/log/py_accountant.json
LOG_ROTATION=size
LOG_MAX_BYTES=104857600
LOGGING_ENABLED=false  # delegated to orchestrator

# FX Audit TTL
FX_TTL_MODE=archive
FX_TTL_RETENTION_DAYS=90
FX_TTL_BATCH_SIZE=1000
FX_TTL_DRY_RUN=false
```

---

## Configuration Variables

### Database Configuration

#### DATABASE_URL

**Purpose**: Sync database connection string for Alembic migrations and sync operations.

**Type**: `str` (SQLAlchemy connection URL)

**Required**: Yes

**Default**: None (test environment: `sqlite+pysqlite:///:memory:`)

**Format**: `dialect+driver://username:password@host:port/database`

**Supported Dialects**:
- SQLite: `sqlite+pysqlite:///./path/to/db.sqlite`
- PostgreSQL: `postgresql+psycopg://user:pass@host:5432/dbname`

**Validation**:
- Must be valid SQLAlchemy URL
- For production: must use PostgreSQL
- For development: SQLite acceptable
- Must NOT use async drivers (asyncpg, aiosqlite)

**Environment Aliases**:
- `PYACC__DATABASE_URL` (with namespace prefix)

**Example**:
```bash
# Development (SQLite)
DATABASE_URL=sqlite+pysqlite:///./accounting.db

# Production (PostgreSQL)
DATABASE_URL=postgresql+psycopg://ledger_user:secure_pass@db.example.com:5432/ledger_prod
```

**Used By**:
- Alembic migrations (`alembic/env.py`)
- Sync use cases (deprecated, for backward compatibility)

**See Also**:
- [DATABASE_URL_ASYNC](#database_url_async) — async runtime connection
- [Alembic Configuration](#alembic-configuration)

---

#### DATABASE_URL_ASYNC

**Purpose**: Async database connection string for runtime operations (AsyncUnitOfWork).

**Type**: `str` (SQLAlchemy async connection URL)

**Required**: Recommended (auto-normalized from DATABASE_URL if not provided)

**Default**: Normalized from DATABASE_URL (psycopg→asyncpg, pysqlite→aiosqlite)

**Format**: `dialect+driver://username:password@host:port/database`

**Supported Dialects**:
- SQLite: `sqlite+aiosqlite:///./path/to/db.sqlite`
- PostgreSQL: `postgresql+asyncpg://user:pass@host:5432/dbname`

**Validation**:
- Must use async driver (aiosqlite, asyncpg)
- Sync drivers (pysqlite, psycopg) will raise error at runtime

**Environment Aliases**:
- `PYACC__DATABASE_URL_ASYNC`

**Example**:
```bash
# Development (SQLite async)
DATABASE_URL_ASYNC=sqlite+aiosqlite:///./accounting.db

# Production (PostgreSQL async)
DATABASE_URL_ASYNC=postgresql+asyncpg://ledger_user:secure_pass@db.example.com:5432/ledger_prod
```

**Used By**:
- AsyncSqlAlchemyUnitOfWork
- All async use cases (AsyncPostTransaction, AsyncGetLedger, etc.)
- Examples: fastapi_basic, cli_basic, telegram_bot

**See Also**:
- [DATABASE_URL](#database_url) — sync connection for migrations
- [DB_POOL_SIZE](#db_pool_size) — connection pooling

---

#### DB_POOL_SIZE

**Purpose**: Number of connections to maintain in the async connection pool.

**Type**: `int`

**Required**: No

**Default**: `5`

**Range**: 1-100 (recommended: 5-20 for typical workloads)

**Environment Aliases**:
- `PYACC__DB_POOL_SIZE`

**Example**:
```bash
# Low traffic
DB_POOL_SIZE=5

# High traffic API
DB_POOL_SIZE=20
```

**Used By**:
- AsyncSqlAlchemyUnitOfWork (create_async_engine)

**Performance Note**: Set based on expected concurrent operations:
```
pool_size = concurrent_requests * avg_request_duration
```

**See Also**:
- [DB_MAX_OVERFLOW](#db_max_overflow)
- [DB_POOL_TIMEOUT](#db_pool_timeout)

---

#### DB_MAX_OVERFLOW

**Purpose**: Maximum number of connections to allow beyond pool_size (temporary overflow).

**Type**: `int`

**Required**: No

**Default**: `10`

**Range**: 0-50 (0 disables overflow)

**Environment Aliases**:
- `PYACC__DB_MAX_OVERFLOW`

**Example**:
```bash
# No overflow (strict pool limit)
DB_MAX_OVERFLOW=0

# Allow 40 overflow connections
DB_MAX_OVERFLOW=40
```

**Note**: Total connections = DB_POOL_SIZE + DB_MAX_OVERFLOW

---

#### DB_POOL_TIMEOUT

**Purpose**: Seconds to wait for connection from pool before raising error.

**Type**: `int` (seconds)

**Required**: No

**Default**: `30`

**Range**: 1-300

**Environment Aliases**:
- `PYACC__DB_POOL_TIMEOUT`

**Example**:
```bash
# Quick timeout for health checks
DB_POOL_TIMEOUT=5

# Longer timeout for batch operations
DB_POOL_TIMEOUT=60
```

---

#### DB_POOL_RECYCLE_SEC

**Purpose**: Seconds before recycling connections (prevents stale connections).

**Type**: `int` (seconds)

**Required**: No

**Default**: `1800` (30 minutes)

**Range**: 300-86400

**Environment Aliases**:
- `PYACC__DB_POOL_RECYCLE_SEC`

**Example**:
```bash
# Recycle every 10 minutes
DB_POOL_RECYCLE_SEC=600

# Recycle every hour
DB_POOL_RECYCLE_SEC=3600
```

**Note**: Important for PostgreSQL with connection limits or firewall timeouts.

---

#### DB_CONNECT_TIMEOUT_SEC

**Purpose**: Maximum seconds to wait when establishing a new database connection.

**Type**: `int` (seconds)

**Required**: No

**Default**: `10`

**Range**: 1-60

**Environment Aliases**:
- `PYACC__DB_CONNECT_TIMEOUT_SEC`

**Example**:
```bash
# Quick connect timeout
DB_CONNECT_TIMEOUT_SEC=5

# Longer timeout for slow networks
DB_CONNECT_TIMEOUT_SEC=30
```

---

#### DB_STATEMENT_TIMEOUT_MS

**Purpose**: PostgreSQL statement timeout in milliseconds (0 = disabled).

**Type**: `int` (milliseconds)

**Required**: No

**Default**: `0` (disabled)

**Range**: 0-300000 (0 = no limit, up to 5 minutes)

**Environment Aliases**:
- `PYACC__DB_STATEMENT_TIMEOUT_MS`

**Example**:
```bash
# Disable timeout
DB_STATEMENT_TIMEOUT_MS=0

# 30 second timeout
DB_STATEMENT_TIMEOUT_MS=30000
```

**Note**: PostgreSQL-specific. Prevents long-running queries.

---

#### DB_RETRY_ATTEMPTS

**Purpose**: Number of retry attempts for transient database errors.

**Type**: `int`

**Required**: No

**Default**: `3`

**Range**: 0-10

**Environment Aliases**:
- `PYACC__DB_RETRY_ATTEMPTS`

**Example**:
```bash
# No retries
DB_RETRY_ATTEMPTS=0

# Retry up to 5 times
DB_RETRY_ATTEMPTS=5
```

**Used For**: Transient errors like connection timeouts, deadlocks.

**See Also**:
- [DB_RETRY_BACKOFF_MS](#db_retry_backoff_ms)
- [DB_RETRY_MAX_BACKOFF_MS](#db_retry_max_backoff_ms)

---

#### DB_RETRY_BACKOFF_MS

**Purpose**: Initial backoff delay in milliseconds between retry attempts.

**Type**: `int` (milliseconds)

**Required**: No

**Default**: `50`

**Range**: 10-5000

**Environment Aliases**:
- `PYACC__DB_RETRY_BACKOFF_MS`

**Example**:
```bash
# Short backoff
DB_RETRY_BACKOFF_MS=50

# Longer backoff
DB_RETRY_BACKOFF_MS=500
```

**Note**: Uses exponential backoff with jitter.

---

#### DB_RETRY_MAX_BACKOFF_MS

**Purpose**: Maximum backoff delay in milliseconds between retry attempts.

**Type**: `int` (milliseconds)

**Required**: No

**Default**: `1000`

**Range**: 100-30000

**Environment Aliases**:
- `PYACC__DB_RETRY_MAX_BACKOFF_MS`

**Example**:
```bash
# Cap at 1 second
DB_RETRY_MAX_BACKOFF_MS=1000

# Cap at 5 seconds
DB_RETRY_MAX_BACKOFF_MS=5000
```

---

### Logging Configuration

#### LOG_LEVEL

**Purpose**: Logging level for py_accountant internal logs.

**Type**: `str` (enum)

**Required**: No

**Default**: `INFO` (test: `DEBUG`, production: `INFO`)

**Allowed Values**: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`

**Environment Aliases**:
- `PYACC__LOG_LEVEL`

**Example**:
```bash
# Development (verbose)
LOG_LEVEL=DEBUG

# Production (minimal)
LOG_LEVEL=WARNING
```

**Used By**:
- Infrastructure logging configuration
- All modules in py_accountant.*

---

#### LOGGING_ENABLED

**Purpose**: Enable or disable py_accountant internal logging bootstrap.

**Type**: `bool`

**Required**: No

**Default**: `true`

**Values**: `true`, `false`, `1`, `0`, `yes`, `no`

**Environment Aliases**:
- `PYACC__LOGGING_ENABLED`

**Example**:
```bash
# Enable internal logging
LOGGING_ENABLED=true

# Disable (when using external logging system)
LOGGING_ENABLED=false
```

**When to Disable**:
- Using external logging (ELK, Datadog, Sentry)
- Custom logging configuration in integrator code
- Duplicate logs issue

**See Also**: [Disabling Internal Logging](#disabling-internal-logging)

---

#### JSON_LOGS

**Purpose**: Output logs in JSON format (for structured logging).

**Type**: `bool`

**Required**: No

**Default**: `false` (test: `false`, production: `true`)

**Environment Aliases**:
- `PYACC__JSON_LOGS`

**Example**:
```bash
# Human-readable logs
JSON_LOGS=false

# Machine-readable JSON
JSON_LOGS=true
```

**Output Format**:
```json
{
  "timestamp": "2025-11-25T10:30:00.123Z",
  "level": "INFO",
  "logger": "py_accountant.application.use_cases_async.ledger",
  "message": "Transaction posted",
  "tx_id": "tx:abc123",
  "amount": "100.00",
  "currency": "USD"
}
```

---

#### LOG_FILE

**Purpose**: Path to log file (optional, logs to stdout if not set).

**Type**: `str` (file path)

**Required**: No

**Default**: `None` (stdout only)

**Environment Aliases**:
- `PYACC__LOG_FILE`

**Example**:
```bash
# Write to file
LOG_FILE=/var/log/py_accountant.log

# JSON log file
LOG_FILE=/var/log/py_accountant.json
```

**Note**: File handler only enabled when `JSON_LOGS=true` and `LOG_FILE` is set.

---

#### LOG_ROTATION

**Purpose**: Log rotation strategy.

**Type**: `str` (enum)

**Required**: No

**Default**: `time`

**Allowed Values**: `time`, `size`

**Environment Aliases**:
- `PYACC__LOG_ROTATION`

**Example**:
```bash
# Rotate by size
LOG_ROTATION=size

# Rotate by time (default)
LOG_ROTATION=time
```

**See Also**:
- [LOG_MAX_BYTES](#log_max_bytes) — for size rotation
- [LOG_ROTATE_WHEN](#log_rotate_when) — for time rotation

---

#### LOG_MAX_BYTES

**Purpose**: Maximum log file size before rotation (size rotation only).

**Type**: `int` (bytes)

**Required**: No (required if LOG_ROTATION=size)

**Default**: `10485760` (10 MB)

**Environment Aliases**:
- `PYACC__LOG_MAX_BYTES`

**Example**:
```bash
# 10 MB rotation (default)
LOG_MAX_BYTES=10485760

# 100 MB rotation
LOG_MAX_BYTES=104857600
```

---

#### LOG_BACKUP_COUNT

**Purpose**: Number of rotated log files to keep.

**Type**: `int`

**Required**: No

**Default**: `7`

**Range**: 1-30

**Environment Aliases**:
- `PYACC__LOG_BACKUP_COUNT`

**Example**:
```bash
# Keep 7 backups (default)
LOG_BACKUP_COUNT=7

# Keep 30 backups
LOG_BACKUP_COUNT=30
```

---

#### LOG_ROTATE_WHEN

**Purpose**: Time-based rotation interval (time rotation only).

**Type**: `str`

**Required**: No (required if LOG_ROTATION=time)

**Default**: `midnight`

**Allowed Values**: `S` (seconds), `M` (minutes), `H` (hours), `D` (days), `midnight`, `W0`-`W6` (weekday)

**Environment Aliases**:
- `PYACC__LOG_ROTATE_WHEN`

**Example**:
```bash
# Rotate at midnight (default)
LOG_ROTATE_WHEN=midnight

# Rotate hourly
LOG_ROTATE_WHEN=H

# Rotate on Mondays
LOG_ROTATE_WHEN=W0
```

---

#### LOG_ROTATE_UTC

**Purpose**: Use UTC for time-based rotation timestamps.

**Type**: `bool`

**Required**: No

**Default**: `true`

**Environment Aliases**:
- `PYACC__LOG_ROTATE_UTC`

**Example**:
```bash
# Use UTC (default)
LOG_ROTATE_UTC=true

# Use local time
LOG_ROTATE_UTC=false
```

---

### Money and Rate Configuration

#### MONEY_SCALE

**Purpose**: Number of decimal places for money amounts.

**Type**: `int`

**Required**: No

**Default**: `2`

**Range**: 0-10

**Environment Aliases**:
- `PYACC__MONEY_SCALE`

**Example**:
```bash
# 2 decimal places (cents)
MONEY_SCALE=2

# 8 decimal places (crypto)
MONEY_SCALE=8
```

**Used By**: Domain quantization (`domain.quantize.money_quantize`)

---

#### RATE_SCALE

**Purpose**: Number of decimal places for exchange rates.

**Type**: `int`

**Required**: No

**Default**: `10`

**Range**: 2-18

**Environment Aliases**:
- `PYACC__RATE_SCALE`

**Example**:
```bash
# 10 decimal places (default)
RATE_SCALE=10

# 6 decimal places
RATE_SCALE=6
```

**Used By**: Domain quantization (`domain.quantize.rate_quantize`)

---

#### ROUNDING

**Purpose**: Decimal rounding mode.

**Type**: `str` (enum)

**Required**: No

**Default**: `ROUND_HALF_EVEN`

**Allowed Values**: `ROUND_HALF_EVEN`, `ROUND_UP`, `ROUND_DOWN`, `ROUND_CEILING`, `ROUND_FLOOR`, `ROUND_HALF_UP`, `ROUND_HALF_DOWN`

**Environment Aliases**:
- `PYACC__ROUNDING`

**Example**:
```bash
# Banker's rounding (default)
ROUNDING=ROUND_HALF_EVEN

# Always round up
ROUNDING=ROUND_UP
```

**Note**: `ROUND_HALF_EVEN` (banker's rounding) minimizes rounding bias over many operations.

---

### FX Audit TTL Configuration

#### FX_TTL_MODE

**Purpose**: Exchange rate events TTL (Time-To-Live) operation mode.

**Type**: `str` (enum)

**Required**: No

**Default**: `none`

**Allowed Values**:
- `none` — No automatic cleanup (manual only)
- `delete` — Delete old events permanently
- `archive` — Archive to archive table, then delete

**Environment Aliases**:
- `PYACC__FX_TTL_MODE`

**Example**:
```bash
# No automatic cleanup
FX_TTL_MODE=none

# Archive old events
FX_TTL_MODE=archive

# Delete permanently
FX_TTL_MODE=delete
```

**Used By**:
- AsyncPlanFxAuditTTL
- AsyncExecuteFxAuditTTL
- Background workers/cron jobs

**See Also**:
- [AsyncPlanFxAuditTTL](API_REFERENCE.md#asyncplanfxauditttl)
- [FX_AUDIT.md](FX_AUDIT.md) — FX audit documentation

---

#### FX_TTL_RETENTION_DAYS

**Purpose**: Number of days to retain exchange rate events before cleanup.

**Type**: `int` (days)

**Required**: No

**Default**: `90`

**Range**: 0-365 (0 = immediate cleanup, 365 = 1 year)

**Environment Aliases**:
- `PYACC__FX_TTL_RETENTION_DAYS`

**Example**:
```bash
# Keep 30 days
FX_TTL_RETENTION_DAYS=30

# Keep 90 days (default)
FX_TTL_RETENTION_DAYS=90

# Keep 1 year
FX_TTL_RETENTION_DAYS=365
```

---

#### FX_TTL_BATCH_SIZE

**Purpose**: Number of events to process per batch during TTL execution.

**Type**: `int`

**Required**: No

**Default**: `1000`

**Range**: 100-10000

**Environment Aliases**:
- `PYACC__FX_TTL_BATCH_SIZE`

**Example**:
```bash
# Small batches (slower, less memory)
FX_TTL_BATCH_SIZE=100

# Large batches (faster, more memory)
FX_TTL_BATCH_SIZE=5000
```

**Performance Note**: Larger batches = faster processing but higher memory usage.

---

#### FX_TTL_DRY_RUN

**Purpose**: Execute TTL planning without actual deletion/archiving (preview mode).

**Type**: `bool`

**Required**: No

**Default**: `false`

**Environment Aliases**:
- `PYACC__FX_TTL_DRY_RUN`

**Example**:
```bash
# Preview mode (no side effects)
FX_TTL_DRY_RUN=true

# Execute mode (actual cleanup)
FX_TTL_DRY_RUN=false
```

**Use Case**: Test TTL configuration before production deployment.

---

## Configuration by Environment

### Development Environment

**File**: `.env.dev`

```bash
# Database (SQLite for simplicity)
DATABASE_URL=sqlite+pysqlite:///./dev.db
DATABASE_URL_ASYNC=sqlite+aiosqlite:///./dev.db

# Logging (verbose)
LOG_LEVEL=DEBUG
LOGGING_ENABLED=true
JSON_LOGS=false

# FX TTL (disabled)
FX_TTL_MODE=none
```

**Usage**:
```bash
# Load .env.dev
export $(cat .env.dev | xargs)
poetry run alembic upgrade head
poetry run python examples/cli_basic/cli.py
```

---

### Staging Environment

**File**: `.env.staging`

```bash
# Database (PostgreSQL)
DATABASE_URL=postgresql+psycopg://ledger:pass@staging-db:5432/ledger_staging
DATABASE_URL_ASYNC=postgresql+asyncpg://ledger:pass@staging-db:5432/ledger_staging

# Connection pooling
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20
DB_POOL_TIMEOUT=30
DB_POOL_RECYCLE_SEC=1800

# Logging (structured)
LOG_LEVEL=INFO
JSON_LOGS=true
LOG_FILE=/var/log/py_accountant_staging.json
LOGGING_ENABLED=true

# FX TTL (test archive mode)
FX_TTL_MODE=archive
FX_TTL_RETENTION_DAYS=30
FX_TTL_DRY_RUN=true
```

---

### Production Environment

**File**: `.env.prod` (use secrets manager instead)

```bash
# Database (PostgreSQL with pooling)
DATABASE_URL=postgresql+psycopg://ledger:${DB_PASSWORD}@prod-db:5432/ledger_prod
DATABASE_URL_ASYNC=postgresql+asyncpg://ledger:${DB_PASSWORD}@prod-db:5432/ledger_prod

# Connection pooling (aggressive)
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=40
DB_POOL_TIMEOUT=30
DB_POOL_RECYCLE_SEC=3600

# Logging (external system)
LOG_LEVEL=WARNING
LOGGING_ENABLED=false  # Datadog/ELK handles logging

# FX TTL (archive mode)
FX_TTL_MODE=archive
FX_TTL_RETENTION_DAYS=90
FX_TTL_BATCH_SIZE=1000
FX_TTL_DRY_RUN=false
```

**Security Note**: Never commit .env.prod! Use secrets manager:
- AWS: Secrets Manager, Parameter Store
- GCP: Secret Manager
- Azure: Key Vault
- Kubernetes: Secrets
- HashiCorp: Vault

---

## Alembic Configuration

### alembic.ini

Alembic reads `DATABASE_URL` from environment. Override in `alembic.ini`:

```ini
[alembic]
script_location = alembic
file_template = %%(year)d%%(month).2d%%(day).2d_%%(hour).2d%%(minute).2d_%%(rev)s_%%(slug)s

# Database URL (can be overridden by env var)
sqlalchemy.url = sqlite+pysqlite:///./dev.db
```

**Best Practice**: Use environment variable, not hardcoded URL.

```bash
# Set DATABASE_URL, then run migrations
export DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/ledger
poetry run alembic upgrade head
```

**Note**: Alembic will reject async drivers. Always use sync URLs (psycopg, pysqlite).

**See Also**: [RUNNING_MIGRATIONS.md](RUNNING_MIGRATIONS.md)

---

## Docker Configuration

### docker-compose.yml

**Example**:
```yaml
version: '3.8'

services:
  db:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: ledger
      POSTGRES_PASSWORD: ledger_pass
      POSTGRES_DB: ledger_dev
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

  app:
    build: .
    env_file:
      - .env.docker
    environment:
      # Override specific vars
      DATABASE_URL: postgresql+psycopg://ledger:ledger_pass@db:5432/ledger_dev
      DATABASE_URL_ASYNC: postgresql+asyncpg://ledger:ledger_pass@db:5432/ledger_dev
      LOG_LEVEL: INFO
    depends_on:
      - db
    ports:
      - "8000:8000"
    command: >
      sh -c "
        poetry run alembic upgrade head &&
        poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000
      "

volumes:
  pgdata:
```

**File**: `.env.docker`

```bash
# Logging
JSON_LOGS=true
LOGGING_ENABLED=true

# FX TTL
FX_TTL_MODE=archive
FX_TTL_RETENTION_DAYS=90
```

**See Also**: [Documented docker-compose.yml](#documented-docker-composeyml)

---

## Advanced Topics

### Disabling Internal Logging

When integrating py_accountant into applications with their own logging infrastructure, you may want to disable internal logging to avoid duplicate or conflicting logs.

**Set Environment Variable**:
```bash
LOGGING_ENABLED=false
# or
PYACC__LOGGING_ENABLED=false
```

**Example Use Cases**:
- Using external logging systems (ELK, Datadog, Sentry)
- Custom logging configuration in integrator code
- Kubernetes sidecar logging

**Note**: UnitOfWork and use cases will still function normally, but won't configure their own log handlers.

---

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

client = hvac.Client(url='https://vault.example.com')
client.auth.approle.login(role_id=ROLE_ID, secret_id=SECRET_ID)

secrets = client.secrets.kv.v2.read_secret_version(path='py_accountant/prod')
data = secrets['data']['data']

os.environ['DATABASE_URL'] = data['database_url']
os.environ['DATABASE_URL_ASYNC'] = data['database_url_async']
```

---

## Troubleshooting

### Common Issues

#### 1. "No async driver found"

**Error**:
```
sqlalchemy.exc.NoSuchModuleError: Can't load plugin: sqlalchemy.dialects:postgresql+asyncpg
```

**Solution**:
```bash
poetry add asyncpg  # for PostgreSQL
poetry add aiosqlite  # for SQLite
```

#### 2. "Connection pool exhausted"

**Error**:
```
sqlalchemy.exc.TimeoutError: QueuePool limit of size 5 overflow 10 reached
```

**Solution**: Increase pool size:
```bash
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=40
```

#### 3. "Alembic can't find DATABASE_URL"

**Error**:
```
sqlalchemy.exc.ArgumentError: Could not parse SQLAlchemy URL from string ''
```

**Solution**: Export environment variable:
```bash
export DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/ledger
```

#### 4. "Logs not appearing"

**Cause**: `LOGGING_ENABLED=false`

**Solution**: Enable logging:
```bash
LOGGING_ENABLED=true
```

#### 5. "Async driver in DATABASE_URL"

**Error**:
```
RuntimeError: DATABASE_URL contains async driver (asyncpg/aiosqlite), but Alembic requires sync URL
```

**Solution**: Use sync driver for DATABASE_URL:
```bash
# Wrong
DATABASE_URL=postgresql+asyncpg://...

# Correct
DATABASE_URL=postgresql+psycopg://...
DATABASE_URL_ASYNC=postgresql+asyncpg://...
```

---

## Validation and Testing

### Validate Configuration

Use the provided validation script:

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

**See Also**: [tools/validate_config.py](#validation-script)

---

## Complete Variable Reference Table

| Variable | Type | Required | Default | Environment | Purpose |
|----------|------|----------|---------|-------------|---------|
| DATABASE_URL | str | Yes | None* | all | Sync DB URL for migrations |
| DATABASE_URL_ASYNC | str | Recommended | Normalized | all | Async DB URL for runtime |
| DB_POOL_SIZE | int | No | 5 | async | Connection pool size |
| DB_MAX_OVERFLOW | int | No | 10 | async | Max overflow connections |
| DB_POOL_TIMEOUT | int | No | 30 | async | Pool timeout (seconds) |
| DB_POOL_RECYCLE_SEC | int | No | 1800 | async | Connection recycle (seconds) |
| DB_CONNECT_TIMEOUT_SEC | int | No | 10 | async | Connect timeout (seconds) |
| DB_STATEMENT_TIMEOUT_MS | int | No | 0 | async | Statement timeout (ms) |
| DB_RETRY_ATTEMPTS | int | No | 3 | async | Retry attempts |
| DB_RETRY_BACKOFF_MS | int | No | 50 | async | Initial backoff (ms) |
| DB_RETRY_MAX_BACKOFF_MS | int | No | 1000 | async | Max backoff (ms) |
| LOG_LEVEL | str | No | INFO | all | Logging level |
| LOGGING_ENABLED | bool | No | true | all | Enable internal logging |
| JSON_LOGS | bool | No | false | all | JSON log format |
| LOG_FILE | str | No | None | all | Log file path |
| LOG_ROTATION | str | No | time | all | Rotation strategy |
| LOG_MAX_BYTES | int | No | 10485760 | all | Max file size (bytes) |
| LOG_BACKUP_COUNT | int | No | 7 | all | Number of backups |
| LOG_ROTATE_WHEN | str | No | midnight | all | Time rotation interval |
| LOG_ROTATE_UTC | bool | No | true | all | Use UTC for rotation |
| MONEY_SCALE | int | No | 2 | all | Decimal places for money |
| RATE_SCALE | int | No | 10 | all | Decimal places for rates |
| ROUNDING | str | No | ROUND_HALF_EVEN | all | Decimal rounding mode |
| FX_TTL_MODE | str | No | none | all | FX TTL mode |
| FX_TTL_RETENTION_DAYS | int | No | 90 | all | Retention days |
| FX_TTL_BATCH_SIZE | int | No | 1000 | all | Batch size |
| FX_TTL_DRY_RUN | bool | No | false | all | Dry run mode |

\* Test environment default: `sqlite+pysqlite:///:memory:`

---

## See Also

- [API_REFERENCE.md](API_REFERENCE.md) — Use cases and protocols
- [INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md) — Integration patterns
- [FX_AUDIT.md](FX_AUDIT.md) — FX audit configuration
- [RUNNING_MIGRATIONS.md](RUNNING_MIGRATIONS.md) — Alembic migrations
- [examples/fastapi_basic/README.md](../examples/fastapi_basic/README.md) — FastAPI example
- [examples/cli_basic/README.md](../examples/cli_basic/README.md) — CLI example
- [examples/telegram_bot/README.md](../examples/telegram_bot/README.md) — Telegram bot example

---

## Навигация

📚 **[← Назад к INDEX](INDEX.md)** | **[API Reference →](API_REFERENCE.md)** | **[Integration Guide →](INTEGRATION_GUIDE.md)**

**См. также**:
- [Tools: validate_config.py](../tools/validate_config.py) — Валидация конфигурации
- [docker-compose.yml](../docker-compose.yml) — Docker setup
- [Tests Documentation](../tests/docs/README.md) — Как тестируется эта документация

---

**Document Version**: 1.1.0-S5  
**Last Updated**: 2025-11-25  
**Maintainer**: py_accountant project team

