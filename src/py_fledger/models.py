from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    create_engine,
    event,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship
from sqlalchemy.pool import StaticPool


class Base(DeclarativeBase):
    pass


class Currency(Base):
    __tablename__ = "currencies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    exchange_rate: Mapped[float | None] = mapped_column("exchangeRate", nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        "createdAt", DateTime(timezone=True), default=func.now(), server_default=func.now(), nullable=False
    )

    accounts: Mapped[list[Account]] = relationship(back_populates="currency")  # type: ignore[name-defined]


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    full_name: Mapped[str] = mapped_column("fullName", String(1024), nullable=False)
    currency_id: Mapped[int] = mapped_column(ForeignKey("currencies.id"), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        "createdAt", DateTime(timezone=True), default=func.now(), server_default=func.now(), nullable=False
    )

    currency: Mapped[Currency] = relationship(back_populates="accounts")
    parent: Mapped[Account | None] = relationship(remote_side=[id], back_populates="children")
    children: Mapped[list[Account]] = relationship(back_populates="parent")
    transactions: Mapped[list[Transaction]] = relationship(back_populates="account")  # type: ignore[name-defined]
    balances: Mapped[list[Balance]] = relationship(back_populates="account")  # type: ignore[name-defined]

    @property
    def path(self) -> list[str]:
        return self.full_name.split(":")


@event.listens_for(Account, "before_insert")
@event.listens_for(Account, "before_update")
def set_full_name(mapper, connection, target: Account):  # noqa: D401, ARG001
    names = []
    parent = target.parent
    while parent is not None:
        names.append(parent.name)
        parent = parent.parent
    names.reverse()
    names.append(target.name)
    target.full_name = ":".join(names)


class JournalEntry(Base):
    __tablename__ = "journalEntries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        "createdAt", DateTime(timezone=True), default=func.now(), server_default=func.now(), nullable=False
    )
    transactions: Mapped[list[Transaction]] = relationship(  # type: ignore[name-defined]
        back_populates="journal", cascade="all, delete-orphan"
    )


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    credit: Mapped[bool] = mapped_column(Boolean, nullable=False)
    memo: Mapped[str | None] = mapped_column(String(1024))
    meta: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    exchange_rate: Mapped[float] = mapped_column("exchangeRate", nullable=False, default=1.0)
    account_id: Mapped[int] = mapped_column("accountId", ForeignKey("accounts.id"), nullable=False)
    journal_id: Mapped[int] = mapped_column("journalId", ForeignKey("journalEntries.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        "createdAt", DateTime(timezone=True), default=func.now(), server_default=func.now(), nullable=False
    )

    account: Mapped[Account] = relationship(back_populates="transactions")
    journal: Mapped[JournalEntry] = relationship(back_populates="transactions")
    balance_records: Mapped[list[Balance]] = relationship(back_populates="transaction")  # type: ignore[name-defined]


class Balance(Base):
    __tablename__ = "balances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    amount: Mapped[int | None] = mapped_column(BigInteger)
    account_id: Mapped[int] = mapped_column("accountId", ForeignKey("accounts.id"), nullable=False)
    transaction_id: Mapped[int | None] = mapped_column("transactionId", ForeignKey("transactions.id"))
    created_at: Mapped[datetime] = mapped_column(
        "createdAt", DateTime(timezone=True), default=func.now(), server_default=func.now(), nullable=False
    )

    account: Mapped[Account] = relationship(back_populates="balances")
    transaction: Mapped[Transaction | None] = relationship(back_populates="balance_records")


class Database:
    def __init__(self, url: str):
        if url.startswith("sqlite") and ":memory:" in url:
            self.engine = create_engine(
                url,
                echo=False,
                future=True,
                connect_args={"check_same_thread": False},
                poolclass=StaticPool,
            )
        else:
            self.engine = create_engine(url, echo=False, future=True)
        self.SessionLocal = Session

    def make_session(self) -> Session:
        return Session(self.engine)

    def create_schema(self) -> None:
        Base.metadata.create_all(self.engine)

    def drop_schema(self) -> None:
        Base.metadata.drop_all(self.engine)

    def dispose(self) -> None:
        self.engine.dispose()
