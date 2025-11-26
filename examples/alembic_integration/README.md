# Alembic Integration Example

This example shows how to integrate py_accountant migrations into your Alembic setup.

## Prerequisites

- Your project already has Alembic configured
- py_accountant installed: `pip install py_accountant`

## Setup

### 1. Modify your `alembic/env.py`

```python
from alembic import context
from py_accountant.infrastructure.migrations import include_in_alembic

def run_migrations_online():
    """Run migrations in 'online' mode."""
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

        with context.begin_transaction():
            # Include py_accountant migrations
            include_in_alembic(context)
            
            # Run migrations (both py_accountant and your own)
            context.run_migrations()
```

### 2. Run migrations

```bash
alembic upgrade head
```

This will apply:
1. All py_accountant migrations (0001-0008)
2. Your project's migrations

## Options

### Table Prefix

If you need to isolate py_accountant tables:

```python
include_in_alembic(context, table_prefix="pyacc_")
```

This will create tables like `pyacc_accounts`, `pyacc_journal_entries`, etc.

### Custom Schema

For multi-schema databases:

```python
include_in_alembic(context, schema="accounting")
```

## Verification

Check which migrations were applied:

```bash
alembic history
```

You should see both py_accountant and your migrations in the history.

## Notes

- py_accountant migrations are applied FIRST (before your migrations)
- Migration IDs are namespaced to avoid conflicts
- All py_accountant migrations are idempotent

