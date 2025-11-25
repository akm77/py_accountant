"""Examples package for py_accountant.

This package contains working examples demonstrating how to integrate
py_accountant into various types of applications.

Available Examples:
------------------
- telegram_bot/ — Telegram bot with aiogram 3.x
  * Demonstrates async-first integration with bot framework
  * UnitOfWork factory pattern for dependency injection
  * Full example with handlers and middleware (planned)

- fastapi_basic/ — REST API with FastAPI
  * Async FastAPI endpoints
  * Dependency injection for use cases
  * Swagger UI auto-documentation
  * Account management endpoints

- cli_basic/ — Command-line interface with Typer
  * Simple CLI for accounting operations
  * Commands for currencies, accounts, and transactions
  * Type-safe argument parsing

Each example is a self-contained application with its own:
- README.md — Setup and usage instructions
- requirements.txt — Dependencies
- Working code demonstrating best practices

Getting Started:
---------------
1. Choose an example that matches your use case
2. Navigate to the example directory (e.g., cd examples/fastapi_basic/)
3. Follow the README.md instructions
4. Apply migrations: alembic upgrade head
5. Run the example application

See Also:
---------
- docs/INTEGRATION_GUIDE.md — General integration patterns
- docs/INTEGRATION_GUIDE_AIOGRAM.md — Detailed Telegram bot guide
- docs/INDEX.md — Complete documentation index
"""

__version__ = "0.1.0"

