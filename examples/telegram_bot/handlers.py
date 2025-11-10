from __future__ import annotations

from datetime import UTC
from decimal import Decimal, InvalidOperation

from application.dto.models import EntryLineDTO
from application.use_cases.ledger import (
    GetBalance,
    PostTransaction,
)
from domain import DomainError
from infrastructure.logging.config import get_logger
from infrastructure.persistence.sqlalchemy.uow import SqlAlchemyUnitOfWork

log = get_logger("bot")


def _new_uow(db_url: str) -> SqlAlchemyUnitOfWork:
    return SqlAlchemyUnitOfWork(db_url)


class _Clock:
    from datetime import datetime, timezone
    tz = UTC
    def now(self):  # noqa: D401
        from datetime import datetime
        return datetime.now(self.tz)

clock = _Clock()


def handle_start(db_url: str) -> str:
    return "py-accountant bot: /balance /tx /rates /audit"


def handle_balance(db_url: str, account: str) -> str:
    uow = _new_uow(db_url)
    try:
        bal = GetBalance(uow, clock)(account)
        uow.commit()
        return f"Balance {account} = {bal}" if bal is not None else "No data"
    except DomainError as e:
        uow.rollback()
        return f"Ошибка: {e}"
    finally:
        uow.close()


def _parse_tx_lines(raw: str) -> list[EntryLineDTO]:
    parts = [p.strip() for p in raw.split(";") if p.strip()]
    lines: list[EntryLineDTO] = []
    for p in parts:
        segs = p.split(":")
        if len(segs) != 5:
            raise DomainError(f"Неверный формат линии: {p}")
        side, acc, amt, cur, rate = segs
        try:
            amount = Decimal(amt)
        except InvalidOperation as e:  # noqa: BLE001
            raise DomainError(f"Неверная сумма: {amt}") from e
        ex_rate = None
        if rate and rate.upper() != "NONE":
            try:
                ex_rate = Decimal(rate)
            except InvalidOperation:
                raise DomainError(f"Неверный курс: {rate}")
        lines.append(EntryLineDTO(side=side.upper(), account_full_name=acc, amount=amount, currency_code=cur.upper(), exchange_rate=ex_rate))
    if len(lines) < 2:
        raise DomainError("Минимум две линии")
    return lines


def handle_tx(db_url: str, raw: str) -> str:
    uow = _new_uow(db_url)
    try:
        lines = _parse_tx_lines(raw)
        post = PostTransaction(uow, clock)
        tx = post(lines, memo="bot")
        uow.commit()
        return f"TX {tx.id} ok ({len(lines)} lines)"
    except DomainError as e:
        uow.rollback()
        return f"Ошибка: {e}"
    finally:
        uow.close()


def handle_rates(db_url: str) -> str:
    uow = _new_uow(db_url)
    try:
        all_cur = uow.currencies.list_all()
        uow.commit()
        rows = [f"{c.code}:{c.exchange_rate or 1}{'*' if c.is_base else ''}" for c in all_cur]
        return "Rates: " + ", ".join(rows)
    finally:
        uow.close()


def handle_audit(db_url: str, limit: int = 10) -> str:
    uow = _new_uow(db_url)
    try:
        repo = uow.exchange_rate_events
        events = repo.list_events(limit=limit)
        uow.commit()
        if not events:
            return "Нет событий"
        rows = [f"{e.code}:{e.rate}@{e.occurred_at.isoformat()}" for e in events]
        return "Audit: " + ", ".join(rows)
    finally:
        uow.close()

