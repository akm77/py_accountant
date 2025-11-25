# FastAPI Basic Example
- [FastAPI Documentation](https://fastapi.tiangolo.com/) — FastAPI framework docs
- [py_accountant Documentation](../../docs/INDEX.md) — Full documentation
- [Integration Guide](../../docs/INTEGRATION_GUIDE.md) — Detailed integration patterns

## See Also

```
pytest tests/
# Run tests

pip install pytest pytest-asyncio httpx
# Install test dependencies
```bash

## Testing

```
Response (AccountResponse)
  ↓
    await uow.commit()
    account = await uc.execute(...)
async with uow:
  ↓
Use Case Factory → AsyncCreateAccount
  ↓
Depends(get_uow) → AsyncSqlAlchemyUnitOfWork
  ↓
Router (app/api/v1/accounts.py)
  ↓
FastAPI Request
```

## Architecture

```
curl http://localhost:8000/api/v1/accounts/
```bash

### List all accounts

```
curl http://localhost:8000/api/v1/accounts/1
```bash

### Get account by ID

```
}
  "currency_code": "USD"
  "full_name": "Assets:Cash",
  "id": 1,
{
```json
Response:

```
  }'
    "currency_code": "USD"
    "full_name": "Assets:Cash",
  -d '{
  -H "Content-Type: application/json" \
curl -X POST http://localhost:8000/api/v1/accounts/ \
```bash

### Create an account

## Usage Examples

- `GET /health` — Health check
- `GET /` — Root endpoint

### Health Check

- `GET /api/v1/accounts/` — List all accounts
- `GET /api/v1/accounts/{id}` — Get account by ID
- `POST /api/v1/accounts/` — Create a new account

### Accounts

## API Endpoints

- **ReDoc**: http://localhost:8000/redoc
- **Swagger UI**: http://localhost:8000/docs
- **API**: http://localhost:8000
The API will be available at:

```
uvicorn app.main:app --host 0.0.0.0 --port 8000
# Production

uvicorn app.main:app --reload
# Development with auto-reload
```bash

## Running the Server

```
alembic upgrade head
# Run migrations

export PYACC__DATABASE_URL=sqlite+pysqlite:///./accounting.db
# For SQLite:
# Note: Alembic needs sync URL
```bash

Before running the app, apply database migrations:

## Running Migrations

```
DB_POOL_TIMEOUT=30
DB_MAX_OVERFLOW=10
DB_POOL_SIZE=20
# Database pool settings

DEBUG=false
APP_NAME=Accounting API
# FastAPI settings

PYACC__DATABASE_URL_ASYNC=sqlite+aiosqlite:///./accounting.db
# Database (async URL for runtime)
```env

Create `.env` file:

## Configuration

```
# Edit .env: set PYACC__DATABASE_URL_ASYNC
cp .env.example .env
# Setup environment

pip install -r requirements.txt
# Install dependencies

cd examples/fastapi_basic
```bash

## Installation

- py_accountant library
- PostgreSQL или SQLite (async)
- Python 3.11+

## Prerequisites

- ✅ Управление транзакциями через AsyncUnitOfWork
- ✅ Автоматическая документация (Swagger UI)
- ✅ REST API для управления счетами
- ✅ Dependency injection с FastAPI
- ✅ Async-first архитектура

## Features

Минимальный пример REST API для управления счетами с использованием `py_accountant`.


