from __future__ import annotations

import warnings
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, asc, desc, func, select
from sqlalchemy.orm import joinedload

from .errors import FError
from .models import (
    Account,
    Balance,
    Currency,
    Database,
    JournalEntry,
    Transaction,
)

# Deprecation notice for the legacy Book API
warnings.warn(
    "py_fledger.Book is deprecated and will be removed in a future release. "
    "Migrate to application use cases (CreateAccount/CreateCurrency/PostTransaction/"
    "GetBalance/ListLedger/GetTradingBalance[Detailed]) and CLI commands.",
    DeprecationWarning,
    stacklevel=2,
)


@dataclass
class SafeAccount:
    name: str
    full_name: str
    path: list[str]
    currency: str | None = None
    children: list[SafeAccount] | None = None


@dataclass
class RichTransaction:
    id: int
    account_name: str
    account_path: list[str]
    amount: int
    credit: bool
    currency: str
    exchange_rate: float
    memo: str | None
    meta: dict[str, Any] | None
    created_at: datetime


class Book:
    def __init__(self, url: str):
        warnings.warn(
            "py_fledger.Book is deprecated. Prefer application.use_cases.* and CLI.",
            DeprecationWarning,
            stacklevel=2,
        )
        if not url:
            raise FError("No DB connection url")
        if not isinstance(url, str):
            raise FError("DB connection url not string")
        self.db = Database(url)

    def init(self) -> None:
        self.db.create_schema()

    def drop(self) -> None:
        self.db.drop_schema()

    def close(self) -> None:
        self.db.dispose()

    def entry(self, memo: str = "") -> Entry:
        return Entry(memo, self)

    # Internal helpers

    def _make_account_path(self, account: str) -> list[str]:
        if not account:
            raise FError("No account provided")
        if not isinstance(account, str):
            raise FError("Account name should be string")
        acc_path = account.split(":")
        if not acc_path:
            raise FError(f"Wrong account {account}")
        return acc_path

    def _find_currency(self, session, code: str | None) -> Currency | None:
        if not code:
            return session.get(Currency, 1)
        if not isinstance(code, str):
            raise FError("Currency code not string")
        stmt = select(Currency).where(Currency.code == code)
        return session.execute(stmt).scalar_one_or_none()

    def _find_account(self, session, account: str) -> Account | None:
        acc_path = self._make_account_path(account)
        parent_id = None
        db_acc: Account | None = None
        for part in acc_path:
            stmt = (
                select(Account)
                .where(and_(Account.name == part, Account.parent_id.is_(parent_id)))
                .options(joinedload(Account.currency))
            )
            db_acc = session.execute(stmt).scalar_one_or_none()
            if not db_acc:
                return None
            parent_id = db_acc.id
        return db_acc

    def _find_subaccounts(self, session, account: Account | None) -> list[Account]:
        prefix = f"{account.full_name}:" if account else ""
        stmt = (
            select(Account)
            .where(Account.full_name.startswith(prefix))
            .order_by(Account.full_name.asc())
            .options(joinedload(Account.currency))
        )
        return list(session.execute(stmt).scalars())

    def create_currency(self, code: str) -> bool:
        with self.db.make_session() as session, session.begin():
            if self._find_currency(session, code):
                raise FError(f"Currency {code} already exists")
            if not code:
                raise FError("No currency code provided")
            if not isinstance(code, str):
                raise FError("Code not string")
            if len(code) > 10:
                raise FError("Code 10 chars max")
            cur = Currency(code=code)
            session.add(cur)
        return True

    def check_currency(self, code: str) -> dict[str, Any] | None:
        with self.db.make_session() as session:
            db_cur = self._find_currency(session, code)
            if not db_cur:
                return None
            return {"code": db_cur.code, "exchangeRate": db_cur.exchange_rate}

    def create_account(self, name: str, currency: str | None = None) -> bool:
        if not name:
            raise FError("Name not specified")
        if not isinstance(name, str):
            raise FError("Name not string")
        if len(name) > 1024:
            raise FError("Name should be <= 255 chars")
        if any(ch for ch in name if not (ch.isalnum() or ch == ":" or ch == "_")):
            raise FError(
                "Name should contain alphanumeric chars and semi-colons as delimeters of account names"
            )
        account_path = name.split(":")
        name_created = account_path[-1]
        if len(name_created) > 255:
            raise FError("Account name cannot be > 255 chars")

        with self.db.make_session() as session, session.begin():
            if self._find_account(session, name):
                raise FError(f"Account {name} already exists")
            parent = None
            if len(account_path) > 1:
                parent = ":".join(account_path[:-1])
            parent_id = None
            parent_obj = None
            if parent:
                parent_obj = self._find_account(session, parent)
                if not parent_obj:
                    raise FError(f"Parent account {parent} not found on DB")
                parent_id = parent_obj.id
            db_currency = self._find_currency(session, currency)
            if not db_currency:
                raise FError(f"Currency {currency} not found")
            account_obj = Account(name=name_created, currency_id=db_currency.id, parent_id=parent_id, full_name="")
            if parent_obj:
                account_obj.parent = parent_obj
            session.add(account_obj)
        return True

    def check_account(self, name: str) -> SafeAccount | None:
        with self.db.make_session() as session:
            db_acc = self._find_account(session, name)
            if not db_acc:
                return None
            return SafeAccount(
                name=db_acc.name,
                full_name=db_acc.full_name,
                path=db_acc.full_name.split(":"),
                currency=db_acc.currency.code if db_acc.currency else None,
            )

    def get_accounts(self, parent: str | None = None) -> list[SafeAccount]:
        with self.db.make_session() as session:
            parent_db = None
            parent_id = None
            if parent:
                parent_db = self._find_account(session, parent)
                if parent_db:
                    parent_id = parent_db.id
            accs = self._find_subaccounts(session, parent_db)

            def find_children(pid: int | None) -> list[SafeAccount]:
                children = [acc for acc in accs if acc.parent_id == pid]
                return [
                    SafeAccount(
                        name=child.name,
                        full_name=child.full_name,
                        path=child.full_name.split(":"),
                        currency=child.currency.code if child.currency else None,
                        children=find_children(child.id),
                    )
                    for child in children
                ]

            return find_children(parent_id)

    def _isolated_balance(self, session, account: Account) -> int:
        from_tx_id = 0
        stmt_bal = (
            select(Balance)
            .where(Balance.account_id == account.id)
            .order_by(Balance.id.desc())
            .limit(1)
        )
        db_bal = session.execute(stmt_bal).scalar_one_or_none()
        if db_bal:
            from_tx_id = db_bal.transaction_id or 0
        stmt_txs = (
            select(Transaction)
            .where(and_(Transaction.account_id == account.id, Transaction.id > from_tx_id))
            .order_by(Transaction.id.desc())
        )
        txs = list(session.execute(stmt_txs).scalars())
        total = 0
        for tx in txs:
            amount = -tx.amount if tx.credit else tx.amount
            total += amount
        if db_bal:
            total += db_bal.amount or 0
        if txs:
            # cache
            bal_row = Balance(
                amount=total, account_id=account.id, transaction_id=txs[0].id  # newest id
            )
            session.add(bal_row)
        return total

    def balance(self, account: str) -> str:
        with self.db.make_session() as session, session.begin():
            db_acc = self._find_account(session, account)
            if not db_acc:
                raise FError(f"Account {account} not found on DB")
            accounts = [db_acc] + self._find_subaccounts(session, db_acc)
            total_base = 0.0
            for acc in accounts:
                bal = self._isolated_balance(session, acc)
                rate = acc.currency.exchange_rate if acc.currency and acc.currency.id != 1 else 1.0
                total_base += bal / rate
            # Return integer-like string preserving JS behaviour which used BN and stringified
            return str(int(round(total_base)))

    def ledger(
        self,
        account: str,
        meta: dict[str, Any] | None = None,
        options: dict[str, Any] | None = None,
    ) -> list[RichTransaction]:
        with self.db.make_session() as session:
            db_acc = self._find_account(session, account)
            if not db_acc:
                raise FError(f"Account {account} not found on DB")
            accounts = [db_acc] + self._find_subaccounts(session, db_acc)
            acc_ids = [acc.id for acc in accounts]
            start_date = datetime.fromtimestamp(0, tz=UTC)
            end_date = datetime.now(UTC)
            offset = 0
            limit = None
            order = desc
            if options:
                if options.get("startDate"):
                    start_date = options["startDate"]
                if options.get("endDate"):
                    end_date = options["endDate"]
                if start_date > end_date:
                    raise FError(
                        f"options.startDate {start_date} should go before options.endDate {end_date}"  # noqa: E501
                    )
                if "offset" in options:
                    _offset = int(options["offset"])
                    if _offset < 0:
                        raise FError("options.offset should be integer number >= 0")
                    offset = _offset
                if "limit" in options:
                    _limit = int(options["limit"])
                    if _limit < 0:
                        raise FError("options.limit should be integer number >= 0")
                    limit = _limit
                if "order" in options:
                    ord_raw = str(options["order"]).upper()
                    order = desc if ord_raw == "DESC" else asc
            meta = meta or {}
            stmt = (
                select(Transaction)
                .where(
                    and_(
                        Transaction.account_id.in_(acc_ids),
                        Transaction.created_at.between(start_date, end_date),
                        *(
                            [Transaction.meta == meta]
                            if meta
                            else []  # empty meta means match all
                        ),
                    )
                )
                .order_by(order(Transaction.created_at))
                .options(joinedload(Transaction.account).joinedload(Account.currency))
                .offset(offset)
            )
            if limit is not None:
                stmt = stmt.limit(limit)
            txs = list(session.execute(stmt).scalars())
            rich: list[RichTransaction] = [
                RichTransaction(
                    id=tx.id,
                    account_name=tx.account.full_name,
                    account_path=tx.account.full_name.split(":"),
                    amount=tx.amount,
                    credit=tx.credit,
                    currency=tx.account.currency.code,
                    exchange_rate=tx.exchange_rate,
                    memo=tx.memo,
                    meta=tx.meta,
                    created_at=tx.created_at,
                )
                for tx in txs
            ]
            return rich

    def trading_balance(self, options: dict[str, Any] | None = None) -> dict[str, Any]:
        start_date = datetime.fromtimestamp(0, tz=UTC)
        end_date = datetime.now(UTC)
        if options:
            if options.get("startDate"):
                start_date = options["startDate"]
            if options.get("endDate"):
                end_date = options["endDate"]
            if start_date > end_date:
                raise FError(
                    f"options.startDate {start_date} should go before options.endDate {end_date}"  # noqa: E501
                )
        result: dict[str, Any] = {"currency": {}, "base": 0}
        with self.db.make_session() as session:
            currencies = list(session.execute(select(Currency)).scalars())
            for currency in currencies:
                # sum credits
                stmt_credits = (
                    select(func.coalesce(func.sum(Transaction.amount), 0))
                    .join(Account)
                    .where(
                        and_(
                            Account.currency_id == currency.id,
                            Transaction.credit.is_(True),
                            Transaction.created_at.between(start_date, end_date),
                        )
                    )
                )
                credits = session.execute(stmt_credits).scalar_one()
                stmt_debits = (
                    select(func.coalesce(func.sum(Transaction.amount), 0))
                    .join(Account)
                    .where(
                        and_(
                            Account.currency_id == currency.id,
                            Transaction.credit.is_(False),
                            Transaction.created_at.between(start_date, end_date),
                        )
                    )
                )
                debits = session.execute(stmt_debits).scalar_one()
                diff = debits - credits
                result["currency"][currency.code] = str(diff)
                rate = currency.exchange_rate if currency.id != 1 else 1.0
                result["base"] += diff / rate
        result["base"] = str(int(round(result["base"])))
        return result


class Entry:
    def __init__(self, memo: str, book: Book):
        if memo is None:
            memo = ""
        if not isinstance(memo, str):
            raise FError("Memo not a string")
        if len(memo) > 1024:
            raise FError("Memo longer than 1024")
        self.memo = memo
        self.debits: list[dict[str, Any]] = []
        self.credits: list[dict[str, Any]] = []
        self._committed = False
        self.book = book

    def debit(self, account: str, amount: int | str, meta: dict[str, Any] | None = None, exchange_rate: float | None = None) -> Entry:
        return self._dir("debits", account, amount, meta, exchange_rate)

    def credit(self, account: str, amount: int | str, meta: dict[str, Any] | None = None, exchange_rate: float | None = None) -> Entry:
        return self._dir("credits", account, amount, meta, exchange_rate)

    def _dir(self, direction: str, account: str, amount: int | str, meta: dict[str, Any] | None, exchange_rate: float | None) -> Entry:
        if not isinstance(account, str):
            raise FError("Account not string")
        try:
            amount_int = int(amount)
        except Exception as exc:  # noqa: BLE001
            raise FError("Amount invalid") from exc
        if amount_int <= 0:
            raise FError("Amount should be > 0")
        if exchange_rate is not None and exchange_rate <= 0:
            raise FError("Exchange rate should be > 0")
        meta = meta or {}
        if not isinstance(meta, dict):
            raise FError("meta is not object")
        getattr(self, direction).append(
            {"account": account, "amount": amount_int, "meta": meta, "exchangeRate": exchange_rate}
        )
        return self

    def _find_accounts(self, session) -> None:
        for direction in [self.debits, self.credits]:
            for el in direction:
                db_acc = self.book._find_account(session, el["account"])  # type: ignore[arg-type]
                if not db_acc:
                    raise FError(f"Account {el['account']} not found on DB")
                el["account"] = db_acc

    def _set_exchange_rates(self) -> None:
        for direction in [self.debits, self.credits]:
            for el in direction:
                acc: Account = el["account"]
                if acc.currency.id == 1:
                    el["exchangeRate"] = 1.0
                elif not el.get("exchangeRate"):
                    rate = acc.currency.exchange_rate
                    if rate is None:
                        raise FError(
                            f"Cannot find exchange rate for account {acc.full_name} in book entry, nor in DB. Perhaps no txs was made with this currency before"  # noqa: E501
                        )
                    el["exchangeRate"] = rate

    def _check_balance(self) -> None:
        def sum_dir(direction: Sequence[dict[str, Any]]) -> float:
            s = 0.0
            for el in direction:
                s += el["amount"] / float(el["exchangeRate"])
            return s

        credit_sum = sum_dir(self.credits)
        debit_sum = sum_dir(self.debits)
        if abs(credit_sum - debit_sum) >= 1e-10:
            raise FError(
                f"Entry not balanced. Credit sum: {credit_sum}, debit sum: {debit_sum}"  # noqa: E501
            )

    def _make_transactions(self) -> list[dict[str, Any]]:
        txs: list[dict[str, Any]] = []
        for direction_name, direction in [("credits", self.credits), ("debits", self.debits)]:
            credit_flag = direction_name == "credits"
            for el in direction:
                acc: Account = el["account"]
                txs.append(
                    {
                        "amount": el["amount"],
                        "credit": credit_flag,
                        "accountId": acc.id,
                        "memo": self.memo,
                        "meta": el["meta"],
                        "exchangeRate": el["exchangeRate"],
                    }
                )
        return txs

    def _update_currency(self, session) -> None:
        if not self._committed:
            raise FError("Cannot update exchange rates before entry committed")
        updates: dict[str, dict[str, Any]] = {}
        for direction in [self.debits, self.credits]:
            for el in direction:
                currency = el["account"].currency
                if currency.code not in updates:
                    updates[currency.code] = {"exchangeRate": None, "currency": currency}
                if currency.id != 1:
                    updates[currency.code]["exchangeRate"] = el["exchangeRate"]
                else:
                    updates[currency.code]["exchangeRate"] = 1.0
        for _code, data in updates.items():  # unused loop var renamed
            data["currency"].exchange_rate = data["exchangeRate"]
            session.add(data["currency"])

    def commit(self) -> None:
        if self._committed:
            raise FError("This entry is already committed")
        with self.book.db.make_session() as session, session.begin():
            self._find_accounts(session)
            self._set_exchange_rates()
            self._check_balance()
            tx_dicts = self._make_transactions()
            journal = JournalEntry()
            session.add(journal)
            session.flush()  # assign id
            for tx in tx_dicts:
                t = Transaction(
                    amount=tx["amount"],
                    credit=tx["credit"],
                    account_id=tx["accountId"],
                    memo=tx["memo"],
                    meta=tx["meta"],
                    exchange_rate=float(tx["exchangeRate"]),
                    journal_id=journal.id,
                )
                session.add(t)
            session.flush()
            self._committed = True
            self._update_currency(session)


def book(url: str) -> Book:
    return Book(url)
