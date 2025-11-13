"""
SQLAlchemy ORM schema declarations only (tables, columns, indexes, optional enums).
No business logic, helpers, or factory functions should live here.

Deprecated: BalanceORM (balances) — kept for backward compatibility; slated for removal
in a future migration after repository simplification (I13+).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class CurrencyORM(Base):
    __tablename__ = "currencies"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    exchange_rate: Mapped[Decimal | None] = mapped_column(Numeric(20, 10), nullable=True)
    is_base: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), server_default=func.now(), nullable=False)


class AccountORM(Base):
    __tablename__ = "accounts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(1024), unique=True, nullable=False)
    currency_code: Mapped[str] = mapped_column(String(10), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), server_default=func.now(), nullable=False)


class JournalORM(Base):
    __tablename__ = "journals"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), server_default=func.now(), nullable=False)
    memo: Mapped[str | None] = mapped_column(String(1024))
    meta: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    # New optional idempotency key for idempotent posting (I-DX-03)
    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True)

    __table_args__ = (
        Index("ix_journals_occurred_at", "occurred_at"),
        UniqueConstraint("idempotency_key", name="uq_journals_idempotency_key"),
    )


class TransactionLineORM(Base):
    __tablename__ = "transaction_lines"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    journal_id: Mapped[int] = mapped_column(Integer, nullable=False)
    account_full_name: Mapped[str] = mapped_column(String(1024), nullable=False)
    side: Mapped[str] = mapped_column(String(6), nullable=False)  # DEBIT/CREDIT
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    currency_code: Mapped[str] = mapped_column(String(10), nullable=False)
    exchange_rate: Mapped[Decimal | None] = mapped_column(Numeric(20, 10), nullable=True)

    __table_args__ = (
        Index("ix_tx_lines_account_full_name", "account_full_name"),
        Index("ix_tx_lines_currency_code", "currency_code"),
        Index("ix_tx_lines_account_journal", "account_full_name", "journal_id"),
    )


class BalanceORM(Base):
    """DEPRECATED: balance cache table.

    Kept temporarily for backward compatibility; removal planned in a later
    iteration with a dedicated migration, after repository simplification (I13+).
    """

    __tablename__ = "balances"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_full_name: Mapped[str] = mapped_column(String(1024), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    last_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("account_full_name", name="uq_balances_account"),
    )


class ExchangeRateEventORM(Base):
    __tablename__ = "exchange_rate_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    rate: Mapped[Decimal] = mapped_column(Numeric(20, 10), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    policy_applied: Mapped[str] = mapped_column(String(64), nullable=False)
    source: Mapped[str | None] = mapped_column(String(64), nullable=True)

    __table_args__ = (
        Index("ix_fx_events_code_occurred_at", "code", "occurred_at"),
    )


class ExchangeRateEventArchiveORM(Base):
    __tablename__ = "exchange_rate_events_archive"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    rate: Mapped[Decimal] = mapped_column(Numeric(20, 10), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    policy_applied: Mapped[str] = mapped_column(String(64), nullable=False)
    source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    archived_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    __table_args__ = (
        Index("ix_fx_events_archive_code_occurred_at", "code", "occurred_at"),
    )
