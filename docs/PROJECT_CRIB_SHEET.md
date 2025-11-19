# Project Crib Sheet

## 1. Environment Variables
- `PYACC__DATABASE_URL` — sync URL for Alembic (PostgreSQL psycopg / SQLite pysqlite).
- `PYACC__DATABASE_URL_ASYNC` — async URL for runtime (PostgreSQL asyncpg / SQLite aiosqlite).
- `PYACC__LOG_LEVEL` — log level (`DEBUG`, `INFO`, ...).
- `PYACC__JSON_LOGS` — `true` to emit JSON logs (enables optional file/rotation settings).
- `PYACC__LOGGING_ENABLED` — set `false` to skip SDK logging bootstrap and plug your own logger.
- `PYACC__FX_TTL_MODE|RETENTION_DAYS|BATCH_SIZE|DRY_RUN` — FX audit TTL policy knobs.
- `PYACC__DB_POOL_SIZE|MAX_OVERFLOW|POOL_TIMEOUT` — async engine tuning. Legacy names without the prefix still work, but `PYACC__` keeps bot and SDK settings separate.

## 2. SDK Bootstrap Snippet
```python
from py_accountant.sdk import bootstrap, use_cases

app = bootstrap.init_app()  # reads env, validates dual URL

async def post_sample_tx():
    async with app.uow_factory() as uow:
        await use_cases.post_transaction(
            uow,
            app.clock,
            ["DEBIT:Assets:Cash:100:USD", "CREDIT:Income:Sales:100:USD"],
            memo="CribSheet",
            meta={"idempotency_key": "cribsheet-001"},
        )
```

## 3. Key Paths
- `src/py_accountant/sdk/bootstrap.py` — `init_app`, `AppContext`.
- `src/py_accountant/sdk/use_cases.py` — async facades for posting, balance, ledger.
- `src/py_accountant/sdk/settings.py` — env loader + dual URL validation.
- `src/infrastructure/config/settings.py` — pydantic settings (env aliases, logging toggle).
- `src/infrastructure/logging/config.py` — structlog bootstrap (honors `LOGGING_ENABLED`).
- `examples/telegram_bot/` — reference bot wiring (config, handlers, README).

