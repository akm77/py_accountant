"""FastAPI application with py_accountant integration.

This example demonstrates:
- Automatic database migrations on startup (via lifespan)
- Schema version validation
- Health check endpoint with migration status
- REST API for accounting operations
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import create_async_engine

from py_accountant import __version_schema__
from py_accountant.infrastructure.migrations import MigrationError, MigrationRunner

from .config import settings

# from .api.v1 import accounts, currencies  # Uncomment if routers are implemented

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: run database migrations on startup."""
    logger.info("Application starting...")

    # Startup: run migrations
    try:
        engine = create_async_engine(settings.database_url_async, echo=False)
        runner = MigrationRunner(engine, echo=False)

        logger.info("Running database migrations...")
        await runner.upgrade_to_head()

        # Validate schema version
        current_version = await runner.get_current_version()
        logger.info(f"Current schema version: {current_version}")

        if current_version != __version_schema__:
            logger.warning(
                f"Schema version mismatch: current={current_version}, "
                f"expected={__version_schema__}"
            )
        else:
            logger.info("✓ Schema version validated")

    except MigrationError as e:
        logger.error(f"Migration failed: {e}")
        raise RuntimeError(f"Failed to initialize database: {e}")

    logger.info("Application started successfully")

    yield

    # Shutdown: cleanup
    logger.info("Application shutting down...")
    await engine.dispose()
    logger.info("Shutdown complete")


# Create FastAPI application
app = FastAPI(
    title="FastAPI + py_accountant Example",
    description="Complete example of integrating py_accountant with FastAPI",
    version="1.0.0",
    lifespan=lifespan,  # Automatic migrations on startup
)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "FastAPI + py_accountant Example",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health")
async def health_check():
    """Health check with migration status."""
    engine = create_async_engine(settings.database_url_async, echo=False)
    runner = MigrationRunner(engine)

    try:
        current = await runner.get_current_version()
        pending = await runner.get_pending_migrations()

        return {
            "status": "healthy" if not pending else "degraded",
            "schema_version": current,
            "expected_version": __version_schema__,
            "pending_migrations": pending,
        }
    finally:
        await engine.dispose()


# Include routers (if they exist - comment out if not implemented)
# app.include_router(accounts.router, prefix="/api/v1", tags=["accounts"])
# app.include_router(currencies.router, prefix="/api/v1", tags=["currencies"])

