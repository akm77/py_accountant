from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from application.dto.models import EntryLineDTO, TransactionDTO
from domain import InMemoryAccountBalanceService


def make_tx(idx: int, account: str, amount: str, side: str = "DEBIT", seconds: int = 0) -> TransactionDTO:
    occurred = datetime.now(UTC) + timedelta(seconds=seconds)
    line = EntryLineDTO(side=side, account_full_name=account, amount=Decimal(amount), currency_code="USD")
    # balancing line to satisfy invariants in real posting (not needed for service direct test but keep consistent)
    bal_line = EntryLineDTO(side="CREDIT" if side == "DEBIT" else "DEBIT", account_full_name="Income:Sales", amount=Decimal(amount), currency_code="USD")
    return TransactionDTO(id=f"t{idx}", occurred_at=occurred, lines=[line, bal_line])


def test_incremental_balance_updates():
    svc = InMemoryAccountBalanceService()
    tx1 = make_tx(1, "Assets:Cash", "100", "DEBIT")
    svc.process_transaction(tx1)
    bal1 = svc.get_balance("Assets:Cash", tx1.occurred_at)
    assert bal1 == Decimal("100")
    # second transaction credit (reduces balance)
    tx2 = make_tx(2, "Assets:Cash", "40", "CREDIT", seconds=5)
    svc.process_transaction(tx2)
    bal2 = svc.get_balance("Assets:Cash", tx2.occurred_at)
    assert bal2 == Decimal("60")


def test_recompute_before_cache_time():
    svc = InMemoryAccountBalanceService()
    tx1 = make_tx(1, "Assets:Cash", "50")
    svc.process_transaction(tx1)
    past_time = tx1.occurred_at - timedelta(seconds=10)
    bal_past = svc.get_balance("Assets:Cash", past_time, recompute=True)
    assert bal_past == Decimal("0")

