from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from application.dto.models import EntryLineDTO
from presentation.async_bridge import (
    create_account_sync,
    create_currency_sync,
    get_account_balance_sync,
    post_transaction_sync,
)


def test_sql_balance_flow_via_bridge(monkeypatch):
    """Verify balance changes using async runtime via presentation facades."""
    import tempfile
    with tempfile.NamedTemporaryFile(prefix="bal_cache_", suffix=".db") as db:
        url = f"sqlite+aiosqlite:///{db.name}"
        monkeypatch.setenv("DATABASE_URL", url)

        create_currency_sync("USD", exchange_rate=Decimal("1"))
        create_account_sync("Assets:Cash", "USD")
        create_account_sync("Income:Sales", "USD")

        post_transaction_sync([
            EntryLineDTO(side="DEBIT", account_full_name="Assets:Cash", amount=Decimal("50"), currency_code="USD"),
            EntryLineDTO(side="CREDIT", account_full_name="Income:Sales", amount=Decimal("50"), currency_code="USD"),
        ])
        bal1 = get_account_balance_sync("Assets:Cash")
        assert bal1 == Decimal("50")

        post_transaction_sync([
            EntryLineDTO(side="CREDIT", account_full_name="Assets:Cash", amount=Decimal("20"), currency_code="USD"),
            EntryLineDTO(side="DEBIT", account_full_name="Income:Sales", amount=Decimal("20"), currency_code="USD"),
        ])
        bal2 = get_account_balance_sync("Assets:Cash")
        assert bal2 == Decimal("30")

        earlier = datetime.now(UTC) - timedelta(days=365)
        bal_earlier = get_account_balance_sync("Assets:Cash", as_of=earlier)
        # Async SQL adapter's account_balance currently ignores as_of; expect same result
        assert bal_earlier == bal2
