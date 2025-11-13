from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from application.dto.models import TransactionDTO


class AccountBalanceServiceProtocol:
    """Protocol-like base (duck type) for balance services.

    Responsibilities:
    - Maintain incremental cached balances per account.
    - Update cache when new transactions are posted.
    - Provide get_balance(account, as_of, recompute=False).
    """

    def process_transaction(self, tx: TransactionDTO) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    def get_balance(self, account_full_name: str, as_of: datetime, recompute: bool = False) -> Decimal:  # pragma: no cover - interface
        raise NotImplementedError


@dataclass
class InMemoryAccountBalanceService(AccountBalanceServiceProtocol):
    """Simple in-memory incremental balance caching.

    Cache structure:
        _cache[account_full_name] = {"balance": Decimal, "last_ts": datetime}
    The balance reflects all processed transactions up to last_ts.
    If get_balance(as_of) is called with a time after last_ts, we recompute from scratch lazily unless recompute=False
    and no new transactions were processed (optimisation kept minimal for now).
    """

    _cache: dict[str, dict[str, Decimal | datetime]] = field(default_factory=dict)
    _all_transactions: list[TransactionDTO] = field(default_factory=list)

    def process_transaction(self, tx: TransactionDTO) -> None:  # noqa: D401
        self._all_transactions.append(tx)
        # Update balances account-wise
        for line in tx.lines:
            bal_entry = self._cache.setdefault(line.account_full_name, {"balance": Decimal("0"), "last_ts": tx.occurred_at})
            balance: Decimal = bal_entry["balance"]  # type: ignore[assignment]
            if line.side.upper() == "DEBIT":
                balance += line.amount
            else:
                balance -= line.amount
            bal_entry["balance"] = balance
            bal_entry["last_ts"] = tx.occurred_at

    def get_balance(self, account_full_name: str, as_of: datetime, recompute: bool = False) -> Decimal:  # noqa: D401
        # Fast path: cached and as_of >= last_ts
        cached = self._cache.get(account_full_name)
        if cached and not recompute and as_of >= cached["last_ts"]:  # type: ignore[index]
            return cached["balance"]  # type: ignore[index]
        # Slow path: recompute from scratch up to as_of
        total = Decimal("0")
        for tx in self._all_transactions:
            if tx.occurred_at > as_of:
                continue
            for line in tx.lines:
                if line.account_full_name != account_full_name:
                    continue
                if line.side.upper() == "DEBIT":
                    total += line.amount
                else:
                    total -= line.amount
        # Update cache
        self._cache[account_full_name] = {"balance": total, "last_ts": as_of}
        return total
