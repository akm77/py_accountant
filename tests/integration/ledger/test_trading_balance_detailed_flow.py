from __future__ import annotations

from decimal import Decimal

import pytest

from application.dto.models import EntryLineDTO
from presentation.async_bridge import (
    create_account_sync,
    create_currency_sync,
    get_trading_balance_detailed_sync,
    post_transaction_sync,
)


@pytest.mark.xfail(reason="REWRITE-DOMAIN (I13): trading aggregation moved out of repositories", strict=False)
def test_trading_balance_detailed_flow_bridge(monkeypatch, tmp_path):
    db_url = f"sqlite+aiosqlite:///{tmp_path}/test.db"
    monkeypatch.setenv("DATABASE_URL", db_url)

    create_currency_sync("USD", exchange_rate=Decimal("1"))
    create_currency_sync("EUR", exchange_rate=Decimal("1.25"))
    create_account_sync("Assets:Cash", "USD")
    create_account_sync("Assets:BankEUR", "EUR")
    create_account_sync("Income:Sales", "USD")

    post_transaction_sync([
        EntryLineDTO(side="DEBIT", account_full_name="Assets:Cash", amount=Decimal("200"), currency_code="USD"),
        EntryLineDTO(side="CREDIT", account_full_name="Income:Sales", amount=Decimal("200"), currency_code="USD"),
    ])
    post_transaction_sync([
        EntryLineDTO(side="DEBIT", account_full_name="Assets:BankEUR", amount=Decimal("100"), currency_code="EUR"),
        EntryLineDTO(side="CREDIT", account_full_name="Income:Sales", amount=Decimal("100"), currency_code="EUR"),
    ])

    tb = get_trading_balance_detailed_sync("USD")
    assert tb.base_currency == "USD"
    assert all(line.converted_balance is not None for line in tb.lines)
    base_total = sum(line.converted_balance for line in tb.lines)  # type: ignore[arg-type]
    assert tb.base_total == base_total
