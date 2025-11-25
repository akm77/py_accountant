# CLI Basic Example
- [Typer Documentation](https://typer.tiangolo.com/) — Typer framework docs
- [py_accountant Documentation](../../docs/INDEX.md) — Full documentation
- [Integration Guide](../../docs/INTEGRATION_GUIDE.md) — Integration patterns

## See Also

```
Display result (typer.echo)
  ↓
    await uow.commit()
    result = await uc.execute(...)
async with uow:
  ↓
Use Case (e.g., AsyncPostTransaction)
  ↓
get_dependencies() → UoW, Repositories
  ↓
asyncio.run() wrapper
  ↓
CLI Command (Typer)
```

## Architecture

```
python cli.py post-transaction --help
python cli.py create-account --help
```bash

Get help for any command:

## Command Help

- `post-transaction --from ID --to ID AMOUNT [--desc TEXT]` — Post a transaction
### Transaction Commands

- `list-accounts` — List all accounts
- `get-account ID` — Get account details
- `create-account FULL_NAME CURRENCY` — Create a new account
### Account Commands

- `list-currencies` — List all currencies
- `create-currency CODE [--base]` — Create a new currency
### Currency Commands

## Available Commands

```
   Description: Save to bank
   3000 from account 1 to account 2
✅ Transaction posted (Entry ID: 2)
$ python cli.py post-transaction --from 1 --to 2 3000 --desc "Save to bank"
# 5. Transfer to bank

   Description: Monthly salary
   5000 from account 3 to account 1
✅ Transaction posted (Entry ID: 1)
$ python cli.py post-transaction --from 3 --to 1 5000 --desc "Monthly salary"
# 4. Post salary transaction

Total: 3 accounts
------------------------------------------------------------
  [  3] Income:Salary                  (USD)
  [  2] Assets:Bank                    (USD)
  [  1] Assets:Cash                    (USD)
------------------------------------------------------------
📊 Accounts:

$ python cli.py list-accounts
# 3. List accounts

✅ Account created: Income:Salary [USD] (ID: 3)
$ python cli.py create-account "Income:Salary" USD

✅ Account created: Assets:Bank [USD] (ID: 2)
$ python cli.py create-account "Assets:Bank" USD

✅ Account created: Assets:Cash [USD] (ID: 1)
$ python cli.py create-account "Assets:Cash" USD
# 2. Create accounts

✅ Currency created: USD (base currency)
$ python cli.py create-currency USD --base
# 1. Setup: Create base currency
```bash

## Example Session

```
python cli.py post-transaction --from 3 --to 1 5000 --desc "Salary payment"
# Post another transaction

python cli.py post-transaction --from 1 --to 2 100.50 --desc "Transfer to bank"
# Post a transaction
```bash

### Transaction Commands

```
python cli.py list-accounts
# List all accounts

python cli.py get-account 1
# Get account details

python cli.py create-account "Income:Salary" USD
python cli.py create-account "Assets:Bank" USD
python cli.py create-account "Assets:Cash" USD
# Create accounts
```bash

### Account Commands

```
python cli.py list-currencies
# List all currencies

python cli.py create-currency EUR
# Create another currency

python cli.py create-currency USD --base
# Create a currency
```bash

### Currency Commands

```
python cli.py --help
```bash

### General Help

## Usage

```
alembic upgrade head
# Run migrations

export PYACC__DATABASE_URL=sqlite+pysqlite:///./accounting.db
# For SQLite:
```bash

Before using the CLI, apply database migrations:

## Running Migrations

To change the database, edit `DATABASE_URL` in `cli.py`:

```python
# For SQLite (default):
DATABASE_URL = "sqlite+aiosqlite:///./accounting.db"

# Or for PostgreSQL:
# DATABASE_URL = "postgresql+asyncpg://user:password@localhost:5432/accounting"
```

By default, the CLI uses SQLite database `./accounting.db`.

## Configuration

```
pip install -r requirements.txt
# Install dependencies

cd examples/cli_basic
```bash

## Installation

- py_accountant library
- SQLite или PostgreSQL (async)
- Python 3.11+

## Prerequisites

- ✅ Type hints и валидация
- ✅ Автоматическая генерация help документации
- ✅ Управление валютами, счетами и транзакциями
- ✅ Простой CLI интерфейс с Typer
- ✅ Async-first архитектура

## Features

Command-line interface для управления учётом с использованием `py_accountant` и `Typer`.


