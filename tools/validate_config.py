#!/usr/bin/env python3
"""Validate environment configuration for py_accountant.

This script validates that all required environment variables are properly set
and conform to expected formats.

Usage:
    python tools/validate_config.py

Exit Codes:
    0 - All validation checks passed
    1 - One or more validation checks failed
"""
from __future__ import annotations

import os
import sys
from urllib.parse import urlparse


def validate_database_url(url: str | None, name: str, async_required: bool = False) -> bool:
    """Validate database URL format.

    Args:
        url: Database URL string to validate
        name: Variable name (for error messages)
        async_required: If True, require async driver

    Returns:
        True if valid, False otherwise
    """
    if not url:
        print(f"❌ {name} is empty or not set")
        return False

    try:
        parsed = urlparse(url)
        scheme = parsed.scheme or ""

        # Check for async drivers
        has_async = any(tok in scheme.lower() for tok in ["asyncpg", "aiosqlite", "+async"])

        if async_required and not has_async:
            print(f"❌ {name} must use async driver (asyncpg, aiosqlite), got: {scheme}")
            return False

        if not async_required and has_async:
            print(f"❌ {name} must use sync driver (psycopg, pysqlite), got: {scheme}")
            return False

        # Validate dialect
        valid_sync_dialects = ["postgresql", "postgresql+psycopg", "sqlite", "sqlite+pysqlite"]
        valid_async_dialects = ["postgresql+asyncpg", "sqlite+aiosqlite"]

        if async_required:
            if scheme not in valid_async_dialects:
                print(f"❌ {name} has invalid async dialect: {scheme}")
                print(f"   Valid async dialects: {', '.join(valid_async_dialects)}")
                return False
        else:
            if scheme not in valid_sync_dialects:
                print(f"❌ {name} has invalid sync dialect: {scheme}")
                print(f"   Valid sync dialects: {', '.join(valid_sync_dialects)}")
                return False

        print(f"✅ Valid {name}: {scheme}://{parsed.hostname or 'file'}")
        return True

    except Exception as e:
        print(f"❌ Invalid {name}: {e}")
        return False


def validate_enum(value: str | None, name: str, allowed_values: list[str], default: str) -> bool:
    """Validate enum configuration value.

    Args:
        value: Configuration value
        name: Variable name (for error messages)
        allowed_values: List of allowed values
        default: Default value

    Returns:
        True if valid, False otherwise
    """
    actual_value = value or default

    if actual_value not in allowed_values:
        print(f"❌ Invalid {name}: {actual_value}")
        print(f"   Allowed values: {', '.join(allowed_values)}")
        return False

    print(f"✅ Valid {name}: {actual_value}")
    return True


def validate_int(value: str | None, name: str, min_val: int, max_val: int, default: int) -> bool:
    """Validate integer configuration value.

    Args:
        value: Configuration value as string
        name: Variable name (for error messages)
        min_val: Minimum allowed value
        max_val: Maximum allowed value
        default: Default value

    Returns:
        True if valid, False otherwise
    """
    if value is None:
        value_int = default
    else:
        try:
            value_int = int(value)
        except ValueError:
            print(f"❌ {name} must be an integer, got: {value}")
            return False

    if not (min_val <= value_int <= max_val):
        print(f"❌ {name} must be between {min_val} and {max_val}, got: {value_int}")
        return False

    print(f"✅ Valid {name}: {value_int}")
    return True


def validate_bool(value: str | None, name: str, default: bool) -> bool:
    """Validate boolean configuration value.

    Args:
        value: Configuration value as string
        name: Variable name (for error messages)
        default: Default value

    Returns:
        True if valid, False otherwise
    """
    if value is None:
        value_bool = default
    else:
        value_lower = value.lower()
        if value_lower in ["true", "1", "yes", "on"]:
            value_bool = True
        elif value_lower in ["false", "0", "no", "off"]:
            value_bool = False
        else:
            print(f"❌ {name} must be boolean (true/false/1/0/yes/no), got: {value}")
            return False

    print(f"✅ Valid {name}: {value_bool}")
    return True


def main() -> int:
    """Validate all required environment variables.

    Returns:
        Exit code (0 = success, 1 = failure)
    """
    print("🔍 Validating py_accountant configuration...\n")

    errors = []

    # =============================================================================
    # Required Variables
    # =============================================================================

    print("📋 Required Variables:")
    print("-" * 60)

    # DATABASE_URL (sync)
    database_url = os.getenv("DATABASE_URL") or os.getenv("PYACC__DATABASE_URL")
    if not validate_database_url(database_url, "DATABASE_URL", async_required=False):
        errors.append("DATABASE_URL invalid or missing")

    # DATABASE_URL_ASYNC (recommended)
    database_url_async = os.getenv("DATABASE_URL_ASYNC") or os.getenv("PYACC__DATABASE_URL_ASYNC")
    if database_url_async:
        if not validate_database_url(database_url_async, "DATABASE_URL_ASYNC", async_required=True):
            errors.append("DATABASE_URL_ASYNC invalid")
    else:
        print("⚠️  DATABASE_URL_ASYNC not set (will be auto-normalized from DATABASE_URL)")

    print()

    # =============================================================================
    # Optional Variables with Validation
    # =============================================================================

    print("📋 Optional Variables:")
    print("-" * 60)

    # LOG_LEVEL
    log_level = os.getenv("LOG_LEVEL") or os.getenv("PYACC__LOG_LEVEL")
    if not validate_enum(
        log_level,
        "LOG_LEVEL",
        ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        "INFO"
    ):
        errors.append("LOG_LEVEL invalid")

    # LOGGING_ENABLED
    logging_enabled = os.getenv("LOGGING_ENABLED") or os.getenv("PYACC__LOGGING_ENABLED")
    if not validate_bool(logging_enabled, "LOGGING_ENABLED", True):
        errors.append("LOGGING_ENABLED invalid")

    # JSON_LOGS
    json_logs = os.getenv("JSON_LOGS") or os.getenv("PYACC__JSON_LOGS")
    if not validate_bool(json_logs, "JSON_LOGS", False):
        errors.append("JSON_LOGS invalid")

    # LOG_ROTATION
    log_rotation = os.getenv("LOG_ROTATION") or os.getenv("PYACC__LOG_ROTATION")
    if not validate_enum(log_rotation, "LOG_ROTATION", ["time", "size"], "time"):
        errors.append("LOG_ROTATION invalid")

    # DB_POOL_SIZE
    db_pool_size = os.getenv("DB_POOL_SIZE") or os.getenv("PYACC__DB_POOL_SIZE")
    if not validate_int(db_pool_size, "DB_POOL_SIZE", 1, 100, 5):
        errors.append("DB_POOL_SIZE invalid")

    # DB_MAX_OVERFLOW
    db_max_overflow = os.getenv("DB_MAX_OVERFLOW") or os.getenv("PYACC__DB_MAX_OVERFLOW")
    if not validate_int(db_max_overflow, "DB_MAX_OVERFLOW", 0, 100, 10):
        errors.append("DB_MAX_OVERFLOW invalid")

    # DB_POOL_TIMEOUT
    db_pool_timeout = os.getenv("DB_POOL_TIMEOUT") or os.getenv("PYACC__DB_POOL_TIMEOUT")
    if not validate_int(db_pool_timeout, "DB_POOL_TIMEOUT", 1, 300, 30):
        errors.append("DB_POOL_TIMEOUT invalid")

    # FX_TTL_MODE
    fx_ttl_mode = os.getenv("FX_TTL_MODE") or os.getenv("PYACC__FX_TTL_MODE")
    if not validate_enum(fx_ttl_mode, "FX_TTL_MODE", ["none", "delete", "archive"], "none"):
        errors.append("FX_TTL_MODE invalid")

    # FX_TTL_RETENTION_DAYS
    fx_ttl_retention = os.getenv("FX_TTL_RETENTION_DAYS") or os.getenv("PYACC__FX_TTL_RETENTION_DAYS")
    if not validate_int(fx_ttl_retention, "FX_TTL_RETENTION_DAYS", 0, 365, 90):
        errors.append("FX_TTL_RETENTION_DAYS invalid")

    # FX_TTL_BATCH_SIZE
    fx_ttl_batch = os.getenv("FX_TTL_BATCH_SIZE") or os.getenv("PYACC__FX_TTL_BATCH_SIZE")
    if not validate_int(fx_ttl_batch, "FX_TTL_BATCH_SIZE", 100, 10000, 1000):
        errors.append("FX_TTL_BATCH_SIZE invalid")

    # FX_TTL_DRY_RUN
    fx_ttl_dry_run = os.getenv("FX_TTL_DRY_RUN") or os.getenv("PYACC__FX_TTL_DRY_RUN")
    if not validate_bool(fx_ttl_dry_run, "FX_TTL_DRY_RUN", False):
        errors.append("FX_TTL_DRY_RUN invalid")

    # MONEY_SCALE
    money_scale = os.getenv("MONEY_SCALE") or os.getenv("PYACC__MONEY_SCALE")
    if not validate_int(money_scale, "MONEY_SCALE", 0, 10, 2):
        errors.append("MONEY_SCALE invalid")

    # RATE_SCALE
    rate_scale = os.getenv("RATE_SCALE") or os.getenv("PYACC__RATE_SCALE")
    if not validate_int(rate_scale, "RATE_SCALE", 2, 18, 10):
        errors.append("RATE_SCALE invalid")

    print()

    # =============================================================================
    # Summary
    # =============================================================================

    if errors:
        print("=" * 60)
        print("❌ Configuration validation FAILED")
        print("=" * 60)
        print("\nErrors found:")
        for error in errors:
            print(f"  - {error}")
        print("\n💡 See docs/CONFIG_REFERENCE.md for configuration details")
        return 1
    else:
        print("=" * 60)
        print("✅ Configuration validation PASSED")
        print("=" * 60)
        print("\n🎉 All configuration checks passed successfully!")
        return 0


if __name__ == "__main__":
    sys.exit(main())

