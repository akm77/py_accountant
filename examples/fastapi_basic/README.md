# FastAPI + py_accountant Example

Complete example of integrating py_accountant with FastAPI.

## Features

- ✅ Automatic database migrations on startup (via `lifespan`)
- ✅ Schema version validation
- ✅ Health check endpoint with migration status
- ✅ REST API for accounting operations
- ✅ Async SQLAlchemy integration

## Prerequisites

- Python 3.11+
- PostgreSQL 13+ (or SQLite)
- Poetry (or pip)

## Setup

### 1. Install dependencies

```bash
cd examples/fastapi_basic
poetry install
```

Or with pip:
```bash
pip install -r requirements.txt
```

### 2. Configure database

```bash
# PostgreSQL
export PYACC__DATABASE_URL_ASYNC="postgresql+asyncpg://user:pass@localhost:5432/mydb"

# SQLite (for testing)
export PYACC__DATABASE_URL_ASYNC="sqlite+aiosqlite:///./test.db"
```

Or create `.env` file:
```
PYACC__DATABASE_URL_ASYNC=sqlite+aiosqlite:///./test.db
DEBUG=true
```

### 3. Run application

```bash
poetry run uvicorn app.main:app --reload
```

Or:
```bash
uvicorn app.main:app --reload
```

The application will:
1. Connect to database
2. Run migrations automatically (via `lifespan`)
3. Validate schema version
4. Start API server

## Usage

### Check health

```bash
curl http://localhost:8000/health
```

Response:
```json
{
  "status": "healthy",
  "schema_version": "0008",
  "expected_version": "0008",
  "pending_migrations": []
}
```

### API Endpoints

- **Root**: http://localhost:8000/
- **Health**: http://localhost:8000/health
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

See http://localhost:8000/docs for interactive API documentation (Swagger UI).

## Migration Behavior

Migrations run automatically on application startup via the `lifespan` context manager:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: run migrations
    runner = MigrationRunner(engine)
    await runner.upgrade_to_head()
    yield
    # Shutdown: cleanup
    await engine.dispose()
```

**Advantages**:
- ✅ Always up-to-date schema
- ✅ No manual migration steps
- ✅ Validates schema on every startup

**Considerations**:
- ⚠️ Startup time increases (usually <1s, but can be longer for large migrations)
- ⚠️ All instances run migrations (use advisory locks in production if needed)

For alternative approaches, see [Migration API Guide](../../docs/MIGRATIONS_API.md).

## Architecture

```
FastAPI Request
  ↓
Router (app/api/v1/accounts.py)
  ↓
Depends(get_uow) → AsyncSqlAlchemyUnitOfWork
  ↓
Use Case Factory → AsyncCreateAccount
  ↓
async with uow:
    account = await uc.execute(...)
    await uow.commit()
  ↓
Response (AccountResponse)
```

## Docker Deployment

### Build image

```bash
docker build -t fastapi-accounting .
```

### Run container

```bash
docker run -p 8000:8000 \
  -e PYACC__DATABASE_URL_ASYNC="postgresql+asyncpg://user:pass@host/db" \
  fastapi-accounting
```

### docker-compose

See `docker-compose.yml` for complete setup with PostgreSQL.

```bash
docker-compose up -d
```

## Troubleshooting

### Migrations not running

**Check logs** for migration output:
```bash
poetry run uvicorn app.main:app --log-level debug
```

### Schema version mismatch

**Manual migration**:
```bash
export DATABASE_URL="postgresql+psycopg://user:pass@localhost:5432/mydb"
python -m py_accountant.infrastructure.migrations upgrade head
```

### Database connection errors

**Verify connection**:
```bash
python -c "from sqlalchemy import create_engine; engine = create_engine('$PYACC__DATABASE_URL_ASYNC'.replace('asyncpg', 'psycopg')); engine.connect()"
```

## Testing

```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run tests
pytest tests/
```

## Learn More

- [Migration API Guide](../../docs/MIGRATIONS_API.md) - Complete migration documentation
- [Integration Guide](../../docs/INTEGRATION_GUIDE.md) - Integration patterns
- [Troubleshooting](../../docs/MIGRATIONS_API.md#troubleshooting) - Common issues

## See Also

- [FastAPI Documentation](https://fastapi.tiangolo.com/) — FastAPI framework docs
- [py_accountant Documentation](../../docs/INDEX.md) — Full documentation
- [Integration Guide](../../docs/INTEGRATION_GUIDE.md) — Detailed integration patterns

## License

Same as py_accountant (see root LICENSE file).

