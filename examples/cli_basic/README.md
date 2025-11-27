# CLI Basic Example

Command-line interface для управления учётом с использованием `py_accountant` и `Typer`.

## Features

- ✅ Async-first архитектура
- ✅ Простой CLI интерфейс с Typer
- ✅ Управление валютами, счетами и транзакциями
- ✅ Database migration commands (init-db, check-db)
- ✅ Автоматическая генерация help документации
- ✅ Type hints и валидация

## Prerequisites

- Python 3.11+
- SQLite или PostgreSQL (async)
- py_accountant library

## Installation

```bash
cd examples/cli_basic

# Install dependencies
pip install -r requirements.txt
```

## Configuration

By default, the CLI uses SQLite database `./accounting.db`.

To change the database, edit `DATABASE_URL` in `cli.py`:

```python
# For SQLite (default):
DATABASE_URL = "sqlite+aiosqlite:///./accounting.db"

# Or for PostgreSQL:
# DATABASE_URL = "postgresql+asyncpg://user:password@localhost:5432/accounting"
```

## Database Setup

### Initialize Database

Run migrations to create tables:

```bash
python cli.py init-db
```

Output:
```
Initializing database...
No migrations applied yet
Running migrations...
✓ Database initialized (version: 0008)
✓ Schema version validated: 0008
```

### Check Migration Status

```bash
python cli.py check-db
```

Output:
```
Current version: 0008
Expected version: 0008
✓ All migrations applied
```

### Alternative: Use Migration CLI

You can also use py_accountant's built-in CLI:

```bash
export DATABASE_URL="sqlite+pysqlite:///./accounting.db"
python -m py_accountant.infrastructure.migrations upgrade head
```

See [Migration API Guide](../../docs/MIGRATIONS_API.md#cli-reference) for all commands.

## Usage

### General Help

```bash
python cli.py --help
```

## Available Commands

### Database Commands

- `init-db` — Initialize database schema (run migrations)
- `check-db` — Check migration status

### Currency Commands

```bash
# Create a currency
python cli.py create-currency USD --base

# Create another currency
python cli.py create-currency EUR

# List all currencies
python cli.py list-currencies
```

### Account Commands

```bash
# Create accounts
python cli.py create-account "Assets:Cash" USD
python cli.py create-account "Assets:Bank" USD
python cli.py create-account "Income:Salary" USD

# Get account details
python cli.py get-account 1

# List all accounts
python cli.py list-accounts
```

### Transaction Commands

```bash
# Post a transaction
python cli.py post-transaction --from 1 --to 2 100.50 --desc "Transfer to bank"

# Post another transaction
python cli.py post-transaction --from 3 --to 1 5000 --desc "Salary payment"
```

## Example Session

```bash
# 1. Setup: Initialize database
$ python cli.py init-db
Initializing database...
✓ Database initialized (version: 0008)

# 2. Create base currency
$ python cli.py create-currency USD --base
✅ Currency created: USD (base currency)

# 3. Create accounts
$ python cli.py create-account "Assets:Cash" USD
✅ Account created: Assets:Cash [USD] (ID: 1)

$ python cli.py create-account "Assets:Bank" USD
✅ Account created: Assets:Bank [USD] (ID: 2)

$ python cli.py create-account "Income:Salary" USD
✅ Account created: Income:Salary [USD] (ID: 3)

# 4. List accounts
$ python cli.py list-accounts

📊 Accounts:
------------------------------------------------------------
  [  1] Assets:Cash                    (USD)
  [  2] Assets:Bank                    (USD)
  [  3] Income:Salary                  (USD)
------------------------------------------------------------
Total: 3 accounts

# 5. Post salary transaction
$ python cli.py post-transaction --from 3 --to 1 5000 --desc "Monthly salary"
✅ Transaction posted (Entry ID: 1)
   5000 from account 3 to account 1
   Description: Monthly salary

# 6. Transfer to bank
$ python cli.py post-transaction --from 1 --to 2 3000 --desc "Save to bank"
✅ Transaction posted (Entry ID: 2)
   3000 from account 1 to account 2
   Description: Save to bank
```

## Command Help

Get help for any command:

```bash
python cli.py create-account --help
python cli.py post-transaction --help
```

## Architecture

```
CLI Command (Typer)
  ↓
asyncio.run() wrapper
  ↓
get_dependencies() → UoW, Repositories
  ↓
Use Case (e.g., AsyncPostTransaction)
  ↓
async with uow:
    result = await uc.execute(...)
    await uow.commit()
  ↓
Display result (typer.echo)
```

## Learn More

- [Migration API Guide](../../docs/MIGRATIONS_API.md) - Complete migration documentation
- [Integration Guide](../../docs/INTEGRATION_GUIDE.md) - Integration patterns
- [Typer Documentation](https://typer.tiangolo.com/) — Typer framework docs
- [py_accountant Documentation](../../docs/INDEX.md) — Full documentation

## See Also

- [FastAPI Example](../fastapi_basic/) — REST API example
- [Telegram Bot Example](../telegram_bot/) — Bot integration example
- [Integration Guide](../../docs/INTEGRATION_GUIDE.md) — Integration patterns

