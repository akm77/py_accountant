# Project Crib Sheet

## 1. Environment Variables
- `PYACC__DATABASE_URL` — sync URL for Alembic (PostgreSQL psycopg / SQLite pysqlite).
- `PYACC__DATABASE_URL_ASYNC` — async URL for runtime (PostgreSQL asyncpg / SQLite aiosqlite).
- `PYACC__LOG_LEVEL` — log level (`DEBUG`, `INFO`, ...).
- `PYACC__JSON_LOGS` — `true` to emit JSON logs (enables optional file/rotation settings).
- `PYACC__LOGGING_ENABLED` — set `false` to skip SDK logging bootstrap and plug your own logger.
- `PYACC__FX_TTL_MODE|RETENTION_DAYS|BATCH_SIZE|DRY_RUN` — FX audit TTL policy knobs.
- `PYACC__DB_POOL_SIZE|MAX_OVERFLOW|POOL_TIMEOUT` — async engine tuning. Legacy names without the prefix still work, but `PYACC__` keeps bot and SDK settings separate.

## 2. Core integration snippet (без SDK)

```python
from application.use_cases.ledger import PostTransaction
from application.ports import UnitOfWork


def post_sample_tx(uow_factory, clock):
    with uow_factory() as uow:  # type: UnitOfWork
        use_case = PostTransaction(uow, clock)
        return use_case(
            lines=[
                # здесь должны быть EntryLineDTO, собранные по вашим правилам
            ],
            memo="CribSheet",
            meta={"idempotency_key": "cribsheet-001"},
        )
```

## 3. Key Paths
- `src/application/ports.py` — контракты UoW и репозиториев.
- `src/application/use_cases/ledger.py` — sync use case'ы по журналу и балансам.
- `src/application/use_cases_async/*.py` — async use case'ы (опционально).
- `src/infrastructure/config/settings.py` — pydantic settings (env aliases, logging toggle).
- `src/infrastructure/logging/config.py` — structlog bootstrap.
- `examples/` — примеры интеграции.
