from sqlalchemy import create_engine, inspect

from infrastructure.persistence.sqlalchemy.models import Base


def test_tables_present_minimal_set():
    """Ensure core tables exist in the ORM schema.

    This test is intentionally minimal to avoid coupling to full schema details.
    If balance cache remains for compatibility, we temporarily assert its presence
    until a dedicated migration removes it in a future iteration (see I13+).
    """
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    insp = inspect(engine)
    actual = set(insp.get_table_names())

    # Adjust names to match alembic migrations and models
    required = {
        "currencies",
        "accounts",
        "journals",
        "transaction_lines",
        "exchange_rate_events",
        "exchange_rate_events_archive",
    }

    missing = required - actual
    assert not missing, f"Missing expected tables: {sorted(missing)}; actual: {sorted(actual)}"
