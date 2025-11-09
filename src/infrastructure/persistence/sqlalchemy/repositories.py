from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from application.dto.models import (
    AccountDTO,
    CurrencyDTO,
    EntryLineDTO,
    RichTransactionDTO,
    TradingBalanceDTO,
    TradingBalanceLineDTO,
    TransactionDTO,
    ExchangeRateEventDTO,
)
from application.interfaces.ports import (
    AccountRepository,
    BalanceRepository,
    CurrencyRepository,
    TransactionRepository,
    ExchangeRateEventsRepository,
)
from infrastructure.persistence.sqlalchemy.models import (
    AccountORM,
    BalanceORM,
    CurrencyORM,
    JournalORM,
    TransactionLineORM,
    ExchangeRateEventORM,
)


class SqlAlchemyCurrencyRepository(CurrencyRepository):  # type: ignore[misc]
    def __init__(self, session: Session):
        self.session = session

    def get_by_code(self, code: str) -> CurrencyDTO | None:  # noqa: D401
        cur = self.session.execute(select(CurrencyORM).where(CurrencyORM.code == code)).scalar_one_or_none()
        if not cur:
            return None
        ex = Decimal(cur.exchange_rate) if cur.exchange_rate is not None else None
        return CurrencyDTO(code=cur.code, exchange_rate=ex, is_base=bool(cur.is_base))

    def upsert(self, dto: CurrencyDTO) -> CurrencyDTO:  # noqa: D401
        cur = self.session.execute(select(CurrencyORM).where(CurrencyORM.code == dto.code)).scalar_one_or_none()
        if not cur:
            cur = CurrencyORM(code=dto.code, exchange_rate=dto.exchange_rate, is_base=dto.is_base)
            self.session.add(cur)
        else:
            cur.exchange_rate = dto.exchange_rate
            cur.is_base = dto.is_base
        # enforce single base if set true
        if dto.is_base:
            self.session.execute(update(CurrencyORM).values(is_base=False))
            cur.is_base = True
            cur.exchange_rate = None
        self.session.flush()
        ex = Decimal(cur.exchange_rate) if cur.exchange_rate is not None else None
        return CurrencyDTO(code=cur.code, exchange_rate=ex, is_base=bool(cur.is_base))

    def list_all(self) -> list[CurrencyDTO]:  # noqa: D401
        rows = self.session.execute(select(CurrencyORM)).scalars().all()
        result: list[CurrencyDTO] = []
        for r in rows:
            ex = Decimal(r.exchange_rate) if r.exchange_rate is not None else None
            result.append(CurrencyDTO(code=r.code, exchange_rate=ex, is_base=bool(r.is_base)))
        return result

    def get_base(self) -> CurrencyDTO | None:  # noqa: D401
        row = self.session.execute(select(CurrencyORM).where(CurrencyORM.is_base.is_(True))).scalar_one_or_none()
        if not row:
            return None
        ex = Decimal(row.exchange_rate) if row.exchange_rate is not None else None
        return CurrencyDTO(code=row.code, exchange_rate=ex, is_base=True)

    def set_base(self, code: str) -> None:  # noqa: D401
        # transactional ensure singleton base
        cur = self.session.execute(select(CurrencyORM).where(CurrencyORM.code == code)).scalar_one_or_none()
        if not cur:
            raise ValueError(f"Currency not found: {code}")
        self.session.execute(update(CurrencyORM).values(is_base=False))
        cur.is_base = True
        cur.exchange_rate = None
        self.session.flush()

    def clear_base(self) -> None:  # noqa: D401
        self.session.execute(update(CurrencyORM).values(is_base=False))
        self.session.flush()

    def bulk_upsert_rates(self, updates: list[tuple[str, Decimal]]) -> None:  # noqa: D401
        for code, rate in updates:
            row = self.session.execute(select(CurrencyORM).where(CurrencyORM.code == code)).scalar_one_or_none()
            if not row:
                row = CurrencyORM(code=code, exchange_rate=rate, is_base=False)
                self.session.add(row)
            else:
                # don't overwrite base
                if not row.is_base:
                    row.exchange_rate = rate
        self.session.flush()


class SqlAlchemyAccountRepository(AccountRepository):  # type: ignore[misc]
    def __init__(self, session: Session):
        self.session = session

    def get_by_full_name(self, full_name: str) -> AccountDTO | None:  # noqa: D401
        acc = self.session.execute(select(AccountORM).where(AccountORM.full_name == full_name)).scalar_one_or_none()
        if not acc:
            return None
        return AccountDTO(id=str(acc.id), name=acc.name, full_name=acc.full_name, currency_code=acc.currency_code, parent_id=str(acc.parent_id) if acc.parent_id else None)

    def create(self, dto: AccountDTO) -> AccountDTO:  # noqa: D401
        acc = self.session.execute(select(AccountORM).where(AccountORM.full_name == dto.full_name)).scalar_one_or_none()
        if acc:
            raise ValueError(f"Account already exists: {dto.full_name}")
        acc = AccountORM(name=dto.name, full_name=dto.full_name, currency_code=dto.currency_code, parent_id=int(dto.parent_id) if dto.parent_id else None)
        self.session.add(acc)
        self.session.flush()
        dto.id = str(acc.id)
        return dto

    def list(self, parent_id: str | None = None) -> list[AccountDTO]:  # noqa: D401
        stmt = select(AccountORM)
        rows = self.session.execute(stmt).scalars().all()
        return [AccountDTO(id=str(r.id), name=r.name, full_name=r.full_name, currency_code=r.currency_code, parent_id=str(r.parent_id) if r.parent_id else None) for r in rows]


class SqlAlchemyBalanceRepository(BalanceRepository):  # type: ignore[misc]
    def __init__(self, session: Session):
        self.session = session

    def upsert_cache(self, account_full_name: str, amount: Decimal, last_ts: datetime) -> None:  # noqa: D401
        row = self.session.execute(select(BalanceORM).where(BalanceORM.account_full_name == account_full_name)).scalar_one_or_none()
        if not row:
            row = BalanceORM(account_full_name=account_full_name, amount=amount, last_ts=last_ts)
            self.session.add(row)
        else:
            row.amount = amount
            row.last_ts = last_ts
        self.session.flush()

    def get_cache(self, account_full_name: str) -> tuple[Decimal, datetime] | None:  # noqa: D401
        row = self.session.execute(select(BalanceORM).where(BalanceORM.account_full_name == account_full_name)).scalar_one_or_none()
        if not row:
            return None
        return (row.amount, row.last_ts)

    def clear(self, account_full_name: str) -> None:  # noqa: D401
        row = self.session.execute(select(BalanceORM).where(BalanceORM.account_full_name == account_full_name)).scalar_one_or_none()
        if row:
            self.session.delete(row)
            self.session.flush()


class SqlAlchemyTransactionRepository(TransactionRepository):  # type: ignore[misc]
    def __init__(self, session: Session):
        self.session = session

    def add(self, dto: TransactionDTO) -> TransactionDTO:  # noqa: D401
        journal = JournalORM(memo=dto.memo, meta=dto.meta, occurred_at=dto.occurred_at)
        self.session.add(journal)
        self.session.flush()
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
        self.session.flush()
        return dto

    def list_between(self, start: datetime, end: datetime, meta: dict[str, Any] | None = None) -> list[TransactionDTO]:  # noqa: D401
        stmt = select(JournalORM).where(JournalORM.occurred_at.between(start, end)).order_by(JournalORM.occurred_at.asc())
        journals = self.session.execute(stmt).scalars().all()
        results: list[TransactionDTO] = []
        for j in journals:
            if meta and any(j.meta.get(k) != v for k, v in meta.items()):
                continue
            lines_stmt = select(TransactionLineORM).where(TransactionLineORM.journal_id == j.id)
            line_rows = self.session.execute(lines_stmt).scalars().all()
            lines = [EntryLineDTO(side=r.side, account_full_name=r.account_full_name, amount=r.amount, currency_code=r.currency_code, exchange_rate=r.exchange_rate) for r in line_rows]
            results.append(TransactionDTO(id=f"journal:{j.id}", occurred_at=j.occurred_at, lines=lines, memo=j.memo, meta=j.meta or {}))
        return results

    def aggregate_trading_balance(self, start: datetime | None, end: datetime | None, base_currency: str | None = None) -> TradingBalanceDTO:  # noqa: D401
        # If no window provided, use full table with current time as as_of
        from datetime import UTC as _UTC
        from datetime import datetime as _DT
        s = start or _DT.fromtimestamp(0, tz=_UTC)
        e = end or _DT.now(tz=_UTC)
        stmt = select(TransactionLineORM).join(JournalORM, JournalORM.id == TransactionLineORM.journal_id).where(JournalORM.occurred_at.between(s, e))
        rows = self.session.execute(stmt).scalars().all()
        debit: dict[str, Decimal] = {}
        credit: dict[str, Decimal] = {}
        for r in rows:
            if r.side == "DEBIT":
                debit[r.currency_code] = debit.get(r.currency_code, Decimal("0")) + r.amount
            else:
                credit[r.currency_code] = credit.get(r.currency_code, Decimal("0")) + r.amount
        lines: list[TradingBalanceLineDTO] = []
        for cur_code in sorted(set(debit.keys()) | set(credit.keys())):
            d = debit.get(cur_code, Decimal("0"))
            c = credit.get(cur_code, Decimal("0"))
            lines.append(TradingBalanceLineDTO(currency_code=cur_code, total_debit=d, total_credit=c, balance=d - c))
        return TradingBalanceDTO(as_of=e, lines=lines, base_currency=base_currency)

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
        j_stmt = select(JournalORM).where(JournalORM.occurred_at.between(start, end))
        if order.upper() == "DESC":
            j_stmt = j_stmt.order_by(JournalORM.occurred_at.desc(), JournalORM.id.desc())
        else:
            j_stmt = j_stmt.order_by(JournalORM.occurred_at.asc(), JournalORM.id.asc())
        journals = self.session.execute(j_stmt).scalars().all()
        results: list[RichTransactionDTO] = []
        for j in journals:
            if meta and any((j.meta or {}).get(k) != v for k, v in meta.items()):
                continue
            lines_stmt = select(TransactionLineORM).where(TransactionLineORM.journal_id == j.id)
            line_rows = self.session.execute(lines_stmt).scalars().all()
            include = any(r.account_full_name == account_full_name for r in line_rows)
            if not include:
                continue
            lines = [EntryLineDTO(side=r.side, account_full_name=r.account_full_name, amount=r.amount, currency_code=r.currency_code, exchange_rate=r.exchange_rate) for r in line_rows]
            results.append(RichTransactionDTO(id=f"journal:{j.id}", occurred_at=j.occurred_at, memo=j.memo, lines=lines, meta=j.meta or {}))
        # Pagination
        if offset < 0:
            return []
        paged = results[offset:]
        if limit is not None:
            if limit <= 0:
                return []
            paged = paged[:limit]
        return paged

    def account_balance(self, account_full_name: str, as_of: datetime) -> Decimal:  # noqa: D401
        stmt = select(TransactionLineORM).where(TransactionLineORM.account_full_name == account_full_name)
        rows = self.session.execute(stmt).scalars().all()
        total = Decimal("0")
        for r in rows:
            if r.side == "DEBIT":
                total += r.amount
            else:
                total -= r.amount
        return total


class SqlAlchemyExchangeRateEventsRepository(ExchangeRateEventsRepository):  # type: ignore[misc]
    def __init__(self, session: Session):
        self.session = session

    def add_event(self, code: str, rate: Decimal, occurred_at: datetime, policy_applied: str, source: str | None) -> ExchangeRateEventDTO:  # noqa: D401
        row = ExchangeRateEventORM(code=code.upper(), rate=rate, occurred_at=occurred_at, policy_applied=policy_applied, source=source)
        self.session.add(row)
        self.session.flush()
        return ExchangeRateEventDTO(id=row.id, code=row.code, rate=row.rate, occurred_at=row.occurred_at, policy_applied=row.policy_applied, source=row.source)

    def list_events(self, code: str | None = None, limit: int | None = None) -> list[ExchangeRateEventDTO]:  # noqa: D401
        stmt = select(ExchangeRateEventORM)
        if code:
            stmt = stmt.where(ExchangeRateEventORM.code == code.upper())
        stmt = stmt.order_by(ExchangeRateEventORM.occurred_at.desc(), ExchangeRateEventORM.id.desc())
        if limit is not None and limit >= 0:
            stmt = stmt.limit(limit)
        rows = self.session.execute(stmt).scalars().all()
        return [ExchangeRateEventDTO(id=r.id, code=r.code, rate=r.rate, occurred_at=r.occurred_at, policy_applied=r.policy_applied, source=r.source) for r in rows]
