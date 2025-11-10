from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from typing import Any

from application.dto.models import (
    AccountDTO,
    CurrencyDTO,
    ExchangeRateEventDTO,
    RichTransactionDTO,
    TradingBalanceDTO,
    TradingBalanceLineDTO,
    TransactionDTO,
)
from application.interfaces.ports import (
    AccountRepository,
    CurrencyRepository,
    ExchangeRateEventsRepository,
    TransactionRepository,
)


class InMemoryCurrencyRepository(CurrencyRepository):  # type: ignore[misc]
    def __init__(self) -> None:
        self._by_code: dict[str, CurrencyDTO] = {}

    def get_by_code(self, code: str) -> CurrencyDTO | None:  # noqa: D401
        return self._by_code.get(code)

    def upsert(self, dto: CurrencyDTO) -> CurrencyDTO:  # noqa: D401
        # ensure singleton base if incoming dto.is_base
        if dto.is_base:
            for c in self._by_code.values():
                c.is_base = False
        self._by_code[dto.code] = dto
        return dto

    def list_all(self) -> list[CurrencyDTO]:  # noqa: D401
        return list(self._by_code.values())

    # Base currency helpers
    def get_base(self) -> CurrencyDTO | None:  # noqa: D401
        for cur in self._by_code.values():
            if cur.is_base:
                return cur
        return None

    def set_base(self, code: str) -> None:  # noqa: D401
        if code not in self._by_code:
            raise ValueError(f"Currency not found: {code}")
        for c in self._by_code.values():
            c.is_base = False
        self._by_code[code].is_base = True
        # base currency typically has exchange_rate = 1 or None
        # we choose None to indicate base intrinsically
        self._by_code[code].exchange_rate = None

    def clear_base(self) -> None:  # noqa: D401
        for c in self._by_code.values():
            c.is_base = False

    def bulk_upsert_rates(self, updates: list[tuple[str, Decimal]]) -> None:  # noqa: D401
        for code, rate in updates:
            dto = self._by_code.get(code) or CurrencyDTO(code=code)
            dto.exchange_rate = rate
            # keep base flag intact
            self._by_code[code] = dto


class InMemoryAccountRepository(AccountRepository):  # type: ignore[misc]
    def __init__(self) -> None:
        self._by_full_name: dict[str, AccountDTO] = {}

    def get_by_full_name(self, full_name: str) -> AccountDTO | None:  # noqa: D401
        return self._by_full_name.get(full_name)

    def create(self, dto: AccountDTO) -> AccountDTO:  # noqa: D401
        if dto.full_name in self._by_full_name:
            raise ValueError(f"Account already exists: {dto.full_name}")
        self._by_full_name[dto.full_name] = dto
        return dto

    def list(self, parent_id: str | None = None) -> list[AccountDTO]:  # noqa: D401
        if parent_id is None:
            return list(self._by_full_name.values())
        return [a for a in self._by_full_name.values() if a.parent_id == parent_id]


class InMemoryTransactionRepository(TransactionRepository):  # type: ignore[misc]
    def __init__(self) -> None:
        self._transactions: dict[str, TransactionDTO] = {}

    def add(self, dto: TransactionDTO) -> TransactionDTO:  # noqa: D401
        if dto.id in self._transactions:
            raise ValueError(f"Transaction already exists: {dto.id}")
        self._transactions[dto.id] = dto
        return dto

    def list_between(self, start: datetime, end: datetime, meta: dict[str, Any] | None = None) -> list[TransactionDTO]:  # noqa: D401
        def meta_match(tx: TransactionDTO) -> bool:
            if not meta:
                return True
            return all(tx.meta.get(k) == v for k, v in meta.items())
        return [t for t in self._transactions.values() if start <= t.occurred_at <= end and meta_match(t)]

    def _rate(self, currencies: CurrencyRepository, code: str) -> Decimal:
        cur = currencies.get_by_code(code)
        if not cur:
            return Decimal("1")
        if cur.is_base:
            return Decimal("1")
        return cur.exchange_rate or Decimal("1")

    def aggregate_trading_balance(self, as_of: datetime, base_currency: str | None = None) -> TradingBalanceDTO:  # noqa: D401
        debit: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
        credit: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
        for tx in self._transactions.values():
            if tx.occurred_at > as_of:
                continue
            for line in tx.lines:
                amt = line.amount
                if line.side.upper() == "DEBIT":
                    debit[line.currency_code] += amt
                else:
                    credit[line.currency_code] += amt
        lines: list[TradingBalanceLineDTO] = []
        for cur in sorted(set(debit.keys()) | set(credit.keys())):
            total_debit = debit[cur]
            total_credit = credit[cur]
            balance = total_debit - total_credit
            lines.append(
                TradingBalanceLineDTO(
                    currency_code=cur,
                    total_debit=total_debit,
                    total_credit=total_credit,
                    balance=balance,
                )
            )
        return TradingBalanceDTO(as_of=as_of, lines=lines, base_currency=base_currency)

    def ledger(
        self,
        account_full_name: str,
        start: datetime,
        end: datetime,
        meta: dict[str, Any] | None = None,
        *,
        offset: int = 0,
        limit: int | None = None,
        order: str = "ASC",
    ) -> list[RichTransactionDTO]:  # noqa: D401
        # Collect matching transactions (rich form) including all lines for context
        tmp: list[RichTransactionDTO] = []
        for tx in self._transactions.values():
            if not (start <= tx.occurred_at <= end):
                continue
            if meta and any(tx.meta.get(k) != v for k, v in meta.items()):
                continue
            include = any(line.account_full_name == account_full_name for line in tx.lines)
            if not include:
                continue
            tmp.append(RichTransactionDTO(id=tx.id, occurred_at=tx.occurred_at, memo=tx.memo, lines=tx.lines, meta=tx.meta))
        # Order
        reverse = order.upper() == "DESC"
        tmp.sort(key=lambda r: r.occurred_at, reverse=reverse)
        # Pagination
        if offset < 0:
            return []  # defensive; validation handled at use case layer
        sliced = tmp[offset:]
        if limit is not None:
            if limit <= 0:
                return []
            sliced = sliced[:limit]
        return sliced

    def account_balance(self, account_full_name: str, as_of: datetime) -> Decimal:  # noqa: D401
        bal = Decimal("0")
        for tx in self._transactions.values():
            if tx.occurred_at > as_of:
                continue
            for line in tx.lines:
                if line.account_full_name != account_full_name:
                    continue
                amt = line.amount
                if line.side.upper() == "DEBIT":
                    bal += amt
                else:
                    bal -= amt
        return bal


class InMemoryExchangeRateEventsRepository(ExchangeRateEventsRepository):  # type: ignore[misc]
    def __init__(self) -> None:
        self._events: list[ExchangeRateEventDTO] = []
        self._archive: list[dict[str, Any]] = []  # simulate archive table rows
        self._next_id = 1

    def add_event(self, code: str, rate: Decimal, occurred_at: datetime, policy_applied: str, source: str | None) -> ExchangeRateEventDTO:  # noqa: D401
        dto = ExchangeRateEventDTO(id=self._next_id, code=code.upper(), rate=rate, occurred_at=occurred_at, policy_applied=policy_applied, source=source)
        self._next_id += 1
        self._events.append(dto)
        return dto

    def list_events(self, code: str | None = None, limit: int | None = None) -> list[ExchangeRateEventDTO]:  # noqa: D401
        items = self._events
        if code:
            up = code.upper()
            items = [e for e in items if e.code == up]
        # newest first
        items = sorted(items, key=lambda e: (e.occurred_at, e.id or 0), reverse=True)
        if limit is not None and limit >= 0:
            items = items[:limit]
        return list(items)

    # TTL helpers
    def list_old_events(self, cutoff: datetime, limit: int) -> list[ExchangeRateEventDTO]:  # noqa: D401
        # normalize cutoff to aware UTC if naive
        if cutoff.tzinfo is None:
            from datetime import UTC
            cutoff = cutoff.replace(tzinfo=UTC)
        items = [e for e in self._events if (e.occurred_at.replace(tzinfo=e.occurred_at.tzinfo or cutoff.tzinfo)) < cutoff]
        items.sort(key=lambda e: (e.occurred_at, e.id or 0))
        return items[: max(0, limit)]

    def delete_events_by_ids(self, ids: list[int]) -> int:  # noqa: D401
        before = len(self._events)
        ids_set = set(ids)
        self._events = [e for e in self._events if (e.id or -1) not in ids_set]
        return before - len(self._events)

    def archive_events(self, rows: list[ExchangeRateEventDTO], archived_at: datetime) -> int:  # noqa: D401
        cnt = 0
        for e in rows:
            if e.id is None:
                continue
            self._archive.append({
                "source_id": e.id,
                "code": e.code,
                "rate": e.rate,
                "occurred_at": e.occurred_at,
                "policy_applied": e.policy_applied,
                "source": e.source,
                "archived_at": archived_at,
            })
            cnt += 1
        return cnt

    def move_events_to_archive(self, cutoff: datetime, limit: int, archived_at: datetime) -> tuple[int, int]:  # noqa: D401
        rows = self.list_old_events(cutoff, limit)
        if not rows:
            return (0, 0)
        archived = self.archive_events(rows, archived_at)
        deleted = self.delete_events_by_ids([int(e.id) for e in rows if e.id is not None])
        return archived, deleted

    # helper for tests
    def _archive_rows(self) -> list[dict[str, Any]]:
        return list(self._archive)

