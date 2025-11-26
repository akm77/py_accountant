# Migration Integration Tests

## Setup

### PostgreSQL Tests

1. Start PostgreSQL:
   ```bash
   cd tests/integration/migrations
   docker-compose up -d
   ```

2. Wait for health check:
   ```bash
   docker-compose ps
   ```

3. Run tests:
   ```bash
   export TEST_POSTGRES_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/test_migrations"
   pytest tests/integration/migrations/test_migrations_postgres.py -v
   ```

4. Stop PostgreSQL:
   ```bash
   docker-compose down -v
   ```

### SQLite Tests

No setup required:
```bash
pytest tests/integration/migrations/test_migrations_sqlite.py -v
```

### E2E Tests

No setup required:
```bash
pytest tests/e2e/migrations/test_cli_workflow.py -v
```

## CI/CD

Tests automatically skip PostgreSQL if not available:
```bash
pytest tests/integration/migrations/ -v  # SQLite only
```

With PostgreSQL (GitHub Actions):
```yaml
services:
  postgres:
    image: postgres:16
    env:
      POSTGRES_PASSWORD: postgres
    ports:
      - 5432:5432
```

## Test Coverage

### PostgreSQL Integration Tests
- Full migration lifecycle (upgrade/downgrade)
- Step-by-step migrations
- Schema verification (tables, indexes)
- Version validation
- Concurrent upgrade safety

### SQLite Integration Tests
- File-based and in-memory databases
- Migration persistence across connections
- URL conversion (aiosqlite → sqlite)
- Schema verification
- Version validation

### E2E CLI Tests
- Upgrade workflow
- Current version check
- Pending migrations
- History display
- Downgrade workflow
- Error handling
- Echo flag functionality

