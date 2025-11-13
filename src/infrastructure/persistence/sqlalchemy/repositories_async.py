"""Asynchronous SQLAlchemy repositories (CRUD-only).

This module provides async counterparts of repositories operating strictly at
CRUD level (create/read/update/delete) with simple filters/sorting/pagination.
Aggregation, conversion, and other domain computations are intentionally
excluded from repositories (moved to domain/use cases per I13).

Notes:
- Public method signatures align with async Protocols in application.ports.
- Some legacy business methods remain as stubs raising NotImplementedError
  and marked DEPRECATED to preserve imports without retaining logic.
- All mutating methods call ``await session.flush()`` within the active txn.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from application.dto.models import (
    AccountDTO,
    CurrencyDTO,
    EntryLineDTO,
    ExchangeRateEventDTO,
    RichTransactionDTO,
    TradingBalanceDTO,
    TransactionDTO,
)
from infrastructure.persistence.sqlalchemy.models import (
    AccountORM,
    CurrencyORM,
    ExchangeRateEventArchiveORM,
    ExchangeRateEventORM,
    JournalORM,
    TransactionLineORM,
)


class AsyncSqlAlchemyCurrencyRepository:
    """Async repository for currency CRUD and base helpers.

    Allowed operations (CRUD-level):
    - get_by_code, upsert, list_all, get_base, set_base, clear_base, bulk_upsert_rates
    - delete(code): convenience method (not in port) kept for tests/utilities.

    Domain rules (like conversion) are not implemented here.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Bind repository to an AsyncSession within a UoW transaction."""
        self.session = session

    async def get_by_code(self, code: str) -> CurrencyDTO | None:
        """Return currency by code or ``None`` if not found."""
        res = await self.session.execute(select(CurrencyORM).where(CurrencyORM.code == code))
        cur = res.scalar_one_or_none()
        if not cur:
            return None
        ex = cur.exchange_rate if cur.exchange_rate is not None else None
        return CurrencyDTO(code=cur.code, exchange_rate=ex, is_base=bool(cur.is_base))

    async def upsert(self, dto: CurrencyDTO) -> CurrencyDTO:
        """Create or update a currency, enforcing base singleton semantics.

        If ``dto.is_base`` is true, all other currencies have ``is_base`` cleared
        and the base currency's ``exchange_rate`` is set to ``None``.
        """
        res = await self.session.execute(select(CurrencyORM).where(CurrencyORM.code == dto.code))
        cur = res.scalar_one_or_none()
        if not cur:
            cur = CurrencyORM(code=dto.code, exchange_rate=dto.exchange_rate, is_base=dto.is_base)
            self.session.add(cur)
        else:
            cur.exchange_rate = dto.exchange_rate
            cur.is_base = dto.is_base
        if dto.is_base:
            await self.session.execute(update(CurrencyORM).values(is_base=False))
            cur.is_base = True
            cur.exchange_rate = None
        await self.session.flush()
        ex = cur.exchange_rate if cur.exchange_rate is not None else None
        return CurrencyDTO(code=cur.code, exchange_rate=ex, is_base=bool(cur.is_base))

    async def list_all(self) -> list[CurrencyDTO]:
        """Return all currencies as ``CurrencyDTO`` list (unordered)."""
        res = await self.session.execute(select(CurrencyORM))
        rows = res.scalars().all()
        result: list[CurrencyDTO] = []
        for r in rows:
            ex = r.exchange_rate if r.exchange_rate is not None else None
            result.append(CurrencyDTO(code=r.code, exchange_rate=ex, is_base=bool(r.is_base)))
        return result

    async def get_base(self) -> CurrencyDTO | None:
        """Return the base currency or ``None`` if not set."""
        res = await self.session.execute(select(CurrencyORM).where(CurrencyORM.is_base.is_(True)))
        row = res.scalar_one_or_none()
        if not row:
            return None
        ex = row.exchange_rate if row.exchange_rate is not None else None
        return CurrencyDTO(code=row.code, exchange_rate=ex, is_base=True)

    async def set_base(self, code: str) -> None:
        """Set specified currency as base and clear others; requires that currency exists."""
        res = await self.session.execute(select(CurrencyORM).where(CurrencyORM.code == code))
        cur = res.scalar_one_or_none()
        if not cur:
            raise ValueError(f"Currency not found: {code}")
        await self.session.execute(update(CurrencyORM).values(is_base=False))
        cur.is_base = True
        cur.exchange_rate = None
        await self.session.flush()

    async def clear_base(self) -> None:
        """Clear base flag from all currencies."""
        await self.session.execute(update(CurrencyORM).values(is_base=False))
        await self.session.flush()

    async def bulk_upsert_rates(self, updates: list[tuple[str, Decimal]]) -> None:
        """Upsert exchange rates for non-base currencies in batch.

        Existing base currency rates are not overridden.
        """
        for code, rate in updates:
            res = await self.session.execute(select(CurrencyORM).where(CurrencyORM.code == code))
            row = res.scalar_one_or_none()
            if not row:
                row = CurrencyORM(code=code, exchange_rate=rate, is_base=False)
                self.session.add(row)
            else:
                if not row.is_base:  # don't overwrite base
                    row.exchange_rate = rate
        await self.session.flush()

    async def delete(self, code: str) -> bool:
        """Delete currency by code; returns True if a row was removed.

        Note: This convenience method is not part of the public port; used in tests.
        """
        res = await self.session.execute(select(CurrencyORM).where(CurrencyORM.code == code))
        row = res.scalar_one_or_none()
        if not row:
            return False
        await self.session.delete(row)  # type: ignore[arg-type]
        await self.session.flush()
        return True


class AsyncSqlAlchemyAccountRepository:
    """Async repository for accounts (CRUD-level).

    Semantics mirror the sync version with uniqueness on ``full_name``.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Bind to ``AsyncSession`` within an active UoW transaction."""
        self.session = session

    async def get_by_full_name(self, full_name: str) -> AccountDTO | None:
        """Return account by its ``full_name`` or ``None`` if absent."""
        res = await self.session.execute(select(AccountORM).where(AccountORM.full_name == full_name))
        acc = res.scalar_one_or_none()
        if not acc:
            return None
        return AccountDTO(
            id=str(acc.id),
            name=acc.name,
            full_name=acc.full_name,
            currency_code=acc.currency_code,
            parent_id=str(acc.parent_id) if acc.parent_id else None,
        )

    async def create(self, dto: AccountDTO) -> AccountDTO:
        """Create a new account; raise ``ValueError`` on duplicate ``full_name``."""
        res = await self.session.execute(select(AccountORM).where(AccountORM.full_name == dto.full_name))
        acc = res.scalar_one_or_none()
        if acc:
            raise ValueError(f"Account already exists: {dto.full_name}")
        acc = AccountORM(
            name=dto.name,
            full_name=dto.full_name,
            currency_code=dto.currency_code,
            parent_id=int(dto.parent_id) if dto.parent_id else None,
        )
        self.session.add(acc)
        await self.session.flush()
        dto.id = str(acc.id)
        return dto

    async def list(self, parent_id: str | None = None) -> list[AccountDTO]:
        """Return accounts optionally filtered by ``parent_id``.

        If ``parent_id`` is provided, returns accounts with that parent_id; otherwise all.
        """
        stmt = select(AccountORM)
        if parent_id is not None:
            try:
                pid = int(parent_id)
            except ValueError:
                # Invalid parent id: return empty list for robustness
                return []
            stmt = stmt.where(AccountORM.parent_id == pid)
        res = await self.session.execute(stmt)
        rows = res.scalars().all()
        return [
            AccountDTO(
                id=str(r.id),
                name=r.name,
                full_name=r.full_name,
                currency_code=r.currency_code,
                parent_id=str(r.parent_id) if r.parent_id else None,
            )
            for r in rows
        ]

    async def delete(self, full_name: str) -> bool:
        """Delete account by ``full_name``; returns True if a row was removed.

        Note: This convenience method is not part of the public port; used in tests.
        """
        res = await self.session.execute(select(AccountORM).where(AccountORM.full_name == full_name))
        row = res.scalar_one_or_none()
        if not row:
            return False
        await self.session.delete(row)  # type: ignore[arg-type]
        await self.session.flush()
        return True



class AsyncSqlAlchemyTransactionRepository:
    """Async repository for financial transactions (CRUD + simple queries).

    Domain aggregations (balances, trading/net, currency conversion) are excluded.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Bind to ``AsyncSession`` within an active UoW transaction."""
        self.session = session

    async def get_by_idempotency_key(self, key: str) -> TransactionDTO | None:
        """Return existing TransactionDTO by idempotency key or None.

        Uses JournalORM.idempotency_key; reconstructs TransactionDTO with stable
        id derived from journal.meta['tx_id'] when present, falling back to
        f"journal:{journal.id}" for legacy rows.
        """
        if not key:
            return None
        res = await self.session.execute(select(JournalORM).where(JournalORM.idempotency_key == key))
        j = res.scalar_one_or_none()
        if not j:
            return None
        lines_stmt = select(TransactionLineORM).where(TransactionLineORM.journal_id == j.id)
        r2 = await self.session.execute(lines_stmt)
        line_rows = r2.scalars().all()
        lines = [
            EntryLineDTO(
                side=r.side,
                account_full_name=r.account_full_name,
                amount=r.amount,
                currency_code=r.currency_code,
                exchange_rate=r.exchange_rate,
            )
            for r in line_rows
        ]
        meta = j.meta or {}
        tx_id = None
        if isinstance(meta, dict):
            tx_id = meta.get("tx_id")
        stable_id = tx_id if isinstance(tx_id, str) and tx_id else f"journal:{j.id}"
        return TransactionDTO(
            id=stable_id,
            occurred_at=j.occurred_at,
            lines=lines,
            memo=j.memo,
            meta=meta or {},
        )

    async def add(self, dto: TransactionDTO) -> TransactionDTO:
        """Insert a Journal with its TransactionLine rows, with idempotency guard.

        If dto.meta contains a non-empty 'idempotency_key', the repository will
        first attempt to find an existing journal by that key and return it. If
        none exists, it will insert a new journal with the key and persist
        dto.id into journal.meta['tx_id'] to ensure stable id on subsequent
        lookups. In case of a concurrent insert, UNIQUE violation is handled by
        reading the existing row and returning it.
        """
        # Normalize idempotency key
        key_raw = str((dto.meta or {}).get("idempotency_key", "")).strip()
        key: str | None = key_raw or None
        if key:
            existing = await self.get_by_idempotency_key(key)
            if existing:
                return existing
        # Prepare meta ensuring tx_id is stored for stable reuse
        journal_meta: dict[str, Any] | None = dict(dto.meta or {})
        if journal_meta is None:
            journal_meta = {}
        if "tx_id" not in journal_meta and dto.id:
            journal_meta["tx_id"] = dto.id
        journal = JournalORM(memo=dto.memo, meta=journal_meta, occurred_at=dto.occurred_at)
        if key:
            journal.idempotency_key = key
        self.session.add(journal)
        try:
            await self.session.flush()
        except IntegrityError:
            # Another transaction inserted the same key concurrently
            if not key:
                raise
            return await self.get_by_idempotency_key(key)  # type: ignore[arg-type]
        for line in dto.lines:
            orm_line = TransactionLineORM(
                journal_id=journal.id,
                account_full_name=line.account_full_name,
                side=line.side.upper(),
                amount=line.amount,
                currency_code=line.currency_code,
                exchange_rate=line.exchange_rate,
            )
            self.session.add(orm_line)
        await self.session.flush()
        return dto

    async def list_between(
        self, start: datetime, end: datetime, meta: dict[str, Any] | None = None
    ) -> list[TransactionDTO]:
        """Return transactions with occurred_at between ``start`` and ``end`` ordered ASC.

        ``meta`` filter: if provided, return only rows where all keys match exactly.
        """
        stmt = (
            select(JournalORM)
            .where(JournalORM.occurred_at.between(start, end))
            .order_by(JournalORM.occurred_at.asc())
        )
        res = await self.session.execute(stmt)
        journals = res.scalars().all()
        results: list[TransactionDTO] = []
        for j in journals:
            if meta and any(j.meta.get(k) != v for k, v in meta.items()):  # type: ignore[union-attr]
                continue
            lines_stmt = select(TransactionLineORM).where(TransactionLineORM.journal_id == j.id)
            r2 = await self.session.execute(lines_stmt)
            line_rows = r2.scalars().all()
            lines = [
                EntryLineDTO(
                    side=r.side,
                    account_full_name=r.account_full_name,
                    amount=r.amount,
                    currency_code=r.currency_code,
                    exchange_rate=r.exchange_rate,
                )
                    for r in line_rows
            ]
            results.append(
                TransactionDTO(
                    id=f"journal:{j.id}",
                    occurred_at=j.occurred_at,
                    lines=lines,
                    memo=j.memo,
                    meta=j.meta or {},
                )
            )
        return results

    async def aggregate_trading_balance(
        self, as_of: datetime, base_currency: str | None = None
    ) -> TradingBalanceDTO:  # noqa: D401
        """DEPRECATED: Aggregation removed from repository in I13.

        This method is intentionally not implemented. Use domain services and
        application use cases to compute trading balances.
        """
        raise NotImplementedError("DEPRECATED in I13: use domain/use cases for aggregation")

    async def ledger(
        self,
        account_full_name: str,
        start: datetime,
        end: datetime,
        meta: dict[str, Any] | None = None,
        *,
        offset: int = 0,
        limit: int | None = None,
        order: str = "ASC",
    ) -> list[RichTransactionDTO]:
        """Return account ledger entries with ordering and pagination.

        - order: "ASC" or "DESC" by occurred_at (and id as a tiebreaker)
        - offset: negative -> return empty list
        - limit: None -> no limit; <= 0 -> empty list
        - meta: all provided key/value pairs must match
        """
        j_stmt = select(JournalORM).where(JournalORM.occurred_at.between(start, end))
        if order.upper() == "DESC":
            j_stmt = j_stmt.order_by(JournalORM.occurred_at.desc(), JournalORM.id.desc())
        else:
            j_stmt = j_stmt.order_by(JournalORM.occurred_at.asc(), JournalORM.id.asc())
        res = await self.session.execute(j_stmt)
        journals = res.scalars().all()
        results: list[RichTransactionDTO] = []
        for j in journals:
            if meta and any((j.meta or {}).get(k) != v for k, v in meta.items()):
                continue
            lines_stmt = select(TransactionLineORM).where(TransactionLineORM.journal_id == j.id)
            r2 = await self.session.execute(lines_stmt)
            line_rows = r2.scalars().all()
            include = any(r.account_full_name == account_full_name for r in line_rows)
            if not include:
                continue
            lines = [
                EntryLineDTO(
                    side=r.side,
                    account_full_name=r.account_full_name,
                    amount=r.amount,
                    currency_code=r.currency_code,
                    exchange_rate=r.exchange_rate,
                )
                for r in line_rows
            ]
            results.append(
                RichTransactionDTO(
                    id=f"journal:{j.id}",
                    occurred_at=j.occurred_at,
                    memo=j.memo,
                    lines=lines,
                    meta=j.meta or {},
                )
            )
        if offset < 0:
            return []
        paged = results[offset:]
        if limit is not None:
            if limit <= 0:
                return []
            paged = paged[:limit]
        return paged

    async def account_balance(self, account_full_name: str, as_of: datetime) -> Decimal:  # noqa: D401
        """DEPRECATED: Balance computation removed from repository in I13.

        This method is intentionally not implemented. Use domain services and
        application use cases to compute account balances.
        """
        raise NotImplementedError("DEPRECATED in I13: use domain/use cases for balance computation")


class AsyncSqlAlchemyExchangeRateEventsRepository:
    """Async repository for FX exchange rate audit trail (CRUD + simple filters).

    TTL/archive orchestration belongs to domain; repository exposes primitive
    read/write operations including the archive table.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Bind to ``AsyncSession`` within an active UoW transaction."""
        self.session = session

    async def add_event(
        self, code: str, rate: Decimal, occurred_at: datetime, policy_applied: str, source: str | None
    ) -> ExchangeRateEventDTO:
        """Insert a new FX event and return its DTO."""
        row = ExchangeRateEventORM(
            code=code.upper(), rate=rate, occurred_at=occurred_at, policy_applied=policy_applied, source=source
        )
        self.session.add(row)
        await self.session.flush()
        return ExchangeRateEventDTO(
            id=row.id,
            code=row.code,
            rate=row.rate,
            occurred_at=row.occurred_at,
            policy_applied=row.policy_applied,
            source=row.source,
        )

    async def list_events(self, code: str | None = None, limit: int | None = None) -> list[ExchangeRateEventDTO]:
        """List FX events filtered by code (optional) ordered newest-first.

        - If ``limit`` is provided and non-negative, it's applied at SQL level.
        - If ``limit`` is negative, an empty list is returned.
        """
        if limit is not None and limit < 0:
            return []
        stmt = select(ExchangeRateEventORM)
        if code:
            stmt = stmt.where(ExchangeRateEventORM.code == code.upper())
        stmt = stmt.order_by(ExchangeRateEventORM.occurred_at.desc(), ExchangeRateEventORM.id.desc())
        if limit is not None:
            stmt = stmt.limit(limit)
        res = await self.session.execute(stmt)
        rows = res.scalars().all()
        return [
            ExchangeRateEventDTO(
                id=r.id,
                code=r.code,
                rate=r.rate,
                occurred_at=r.occurred_at,
                policy_applied=r.policy_applied,
                source=r.source,
            )
            for r in rows
        ]

    async def list_old_events(self, cutoff: datetime, limit: int) -> list[ExchangeRateEventDTO]:
        """Return oldest-first rows strictly older than ``cutoff`` up to ``limit``."""
        if cutoff.tzinfo is None:
            from datetime import UTC

            cutoff = cutoff.replace(tzinfo=UTC)
        stmt = (
            select(ExchangeRateEventORM)
            .where(ExchangeRateEventORM.occurred_at < cutoff)
            .order_by(ExchangeRateEventORM.occurred_at.asc(), ExchangeRateEventORM.id.asc())
            .limit(max(0, limit))
        )
        res = await self.session.execute(stmt)
        rows = res.scalars().all()
        return [
            ExchangeRateEventDTO(
                id=r.id,
                code=r.code,
                rate=r.rate,
                occurred_at=r.occurred_at,
                policy_applied=r.policy_applied,
                source=r.source,
            )
            for r in rows
        ]

    async def delete_events_by_ids(self, ids: list[int]) -> int:
        """Delete events by primary key IDs and return the number of deleted rows."""
        if not ids:
            return 0
        stmt = select(ExchangeRateEventORM).where(ExchangeRateEventORM.id.in_(ids))
        res = await self.session.execute(stmt)
        rows = res.scalars().all()
        for r in rows:
            await self.session.delete(r)  # type: ignore[arg-type]
        await self.session.flush()
        return len(rows)

    async def archive_events(self, rows: list[ExchangeRateEventDTO], archived_at: datetime) -> int:
        """Copy provided FX events into archive table; return number of rows archived."""
        if not rows:
            return 0
        objs: list[ExchangeRateEventArchiveORM] = []
        for e in rows:
            if e.id is None:
                continue
            objs.append(
                ExchangeRateEventArchiveORM(
                    source_id=int(e.id),
                    code=e.code,
                    rate=e.rate,
                    occurred_at=e.occurred_at,
                    policy_applied=e.policy_applied,
                    source=e.source,
                    archived_at=archived_at,
                )
            )
        if not objs:
            return 0
        self.session.add_all(objs)
        await self.session.flush()
        return len(objs)

    async def move_events_to_archive(
        self, cutoff: datetime, limit: int, archived_at: datetime
    ) -> tuple[int, int]:  # noqa: D401
        """DEPRECATED: Orchestration moved to domain in I13.

        Use list_old_events + archive_events + delete_events_by_ids from a
        domain service or use case layer.
        """
        raise NotImplementedError("DEPRECATED in I13: move orchestration to domain/use cases")
