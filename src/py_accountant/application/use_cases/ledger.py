from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

from py_accountant.application.dto.models import (
    AccountDTO,
    CurrencyDTO,
    EntryLineDTO,
    RichTransactionDTO,
    TradingBalanceLineDetailed,
    TradingBalanceLineSimple,
    TransactionDTO,
)
from py_accountant.application.ports import Clock
from py_accountant.application.ports import SupportsCommitRollback as UnitOfWork
from py_accountant.domain import (
    AccountName,
    CurrencyCode,
    DomainError,
    EntryLine,
    EntrySide,
    ExchangeRate,
    TransactionVO,
)
from py_accountant.domain.ledger import LedgerEntry
from py_accountant.domain.services.account_balance_service import (
    AccountBalanceServiceProtocol,
    InMemoryAccountBalanceService,
)
from py_accountant.domain.services.exchange_rate_policy import ExchangeRatePolicy
from py_accountant.domain.trading_balance import ConvertedAggregator, RawAggregator

# Mappers

def map_account_vo_to_dto(full_name: AccountName, currency: CurrencyCode, id: str | None = None, parent_id: str | None = None) -> AccountDTO:
    return AccountDTO(id=id or full_name.full_name, name=full_name.name, full_name=full_name.full_name, currency_code=currency.code, parent_id=parent_id)


def map_currency_vo_to_dto(code: CurrencyCode) -> CurrencyDTO:
    return CurrencyDTO(code=code.code)


def map_line_dto_to_vo(line: EntryLineDTO) -> EntryLine:
    side = EntrySide(line.side.upper())
    account = AccountName(line.account_full_name)
    currency = CurrencyCode(line.currency_code)
    ex_rate = ExchangeRate.from_number(line.exchange_rate or 1)
    return EntryLine.create(side, account, line.amount, currency, ex_rate)


# Use cases

@dataclass
class CreateCurrency:
    uow: UnitOfWork

    def __call__(self, code: str, exchange_rate: Decimal | None = None) -> CurrencyDTO:
        vo = CurrencyCode(code)
        existing = self.uow.currencies.get_by_code(vo.code)
        if existing:
            if exchange_rate is not None:
                existing.exchange_rate = exchange_rate
            return existing
        dto = map_currency_vo_to_dto(vo)
        dto.exchange_rate = exchange_rate
        return self.uow.currencies.upsert(dto)


@dataclass
class CreateAccount:
    uow: UnitOfWork

    def __call__(self, full_name: str, currency_code: str) -> AccountDTO:
        full = AccountName(full_name)
        if self.uow.accounts.get_by_full_name(full.full_name):
            raise DomainError(f"Account already exists: {full}")
        cur = self.uow.currencies.get_by_code(CurrencyCode(currency_code).code)
        if not cur:
            raise DomainError(f"Currency not found: {currency_code}")
        dto = map_account_vo_to_dto(full, CurrencyCode(cur.code))
        return self.uow.accounts.create(dto)


@dataclass
class PostTransaction:
    uow: UnitOfWork
    clock: Clock
    balance_service: AccountBalanceServiceProtocol | InMemoryAccountBalanceService | None = None
    rate_policy: ExchangeRatePolicy | None = None

    def __call__(self, lines: list[EntryLineDTO], memo: str | None = None, meta: dict | None = None) -> TransactionDTO:
        if not lines:
            raise DomainError("No lines provided")
        for line in lines:
            if not self.uow.accounts.get_by_full_name(line.account_full_name):
                raise DomainError(f"Account not found: {line.account_full_name}")
            if not self.uow.currencies.get_by_code(line.currency_code):
                raise DomainError(f"Currency not found: {line.currency_code}")
        vo_lines = [map_line_dto_to_vo(line) for line in lines]
        tx_vo = TransactionVO.from_lines(vo_lines, memo or "", self.clock.now())
        tx_dto = TransactionDTO(
            id=f"tx:{uuid4().hex}",
            occurred_at=tx_vo.occurred_at,
            lines=lines,
            memo=memo,
            meta=meta or {},
        )
        saved = self.uow.transactions.add(tx_dto)
        if self.balance_service:
            self.balance_service.process_transaction(saved)
        if self.rate_policy:
            updater = UpdateCurrenciesFromTransaction(self.uow, self.rate_policy)
            updater(saved)
        return saved


@dataclass
class UpdateCurrenciesFromTransaction:
    uow: UnitOfWork
    policy: ExchangeRatePolicy | None = None

    def __call__(self, tx: TransactionDTO) -> None:
        for line in tx.lines:
            if line.exchange_rate and line.exchange_rate > 0:
                cur = self.uow.currencies.get_by_code(line.currency_code)
                if cur:
                    if self.policy:
                        cur.exchange_rate = self.policy.apply(cur.exchange_rate, line.exchange_rate)
                    else:
                        cur.exchange_rate = line.exchange_rate
                    self.uow.currencies.upsert(cur)


@dataclass
class GetBalance:
    uow: UnitOfWork
    clock: Clock
    balance_service: AccountBalanceServiceProtocol | InMemoryAccountBalanceService | None = None

    def __call__(self, account_full_name: str, as_of: datetime | None = None, recompute: bool = False) -> Decimal:
        query_time = as_of or self.clock.now()
        if self.balance_service is not None:
            return self.balance_service.get_balance(account_full_name, query_time, recompute=recompute)
        return self.uow.transactions.account_balance(account_full_name, query_time)


@dataclass
class GetLedger:
    uow: UnitOfWork
    clock: Clock

    def __call__(self, account_full_name: str, start: datetime | None = None, end: datetime | None = None, meta: dict | None = None) -> list[RichTransactionDTO]:
        start_dt = start or datetime.fromtimestamp(0, tz=self.clock.now().tzinfo)
        end_dt = end or self.clock.now()
        return self.uow.transactions.ledger(account_full_name, start_dt, end_dt, meta)


@dataclass
class ListLedger:
    """Расширенный доступ к журналу с пагинацией, сортировкой и фильтрами.

    Валидация параметров перед делегированием в репозиторий.
    """
    uow: UnitOfWork
    clock: Clock

    def __call__(
        self,
        account_full_name: str,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        meta: dict[str, Any] | None = None,
        offset: int = 0,
        limit: int | None = None,
        order: str = "ASC",
    ) -> list[RichTransactionDTO]:
        if not account_full_name or ":" not in account_full_name:
            raise DomainError("Invalid account_full_name format")
        start_dt = start or datetime.fromtimestamp(0, tz=self.clock.now().tzinfo)
        end_dt = end or self.clock.now()
        if start_dt > end_dt:
            raise DomainError("start > end")
        if offset < 0:
            raise DomainError("offset must be >= 0")
        if limit is not None and limit < 0:
            raise DomainError("limit must be >= 0")
        order_up = order.upper()
        if order_up not in {"ASC", "DESC"}:
            raise DomainError("order must be ASC or DESC")
        if meta is not None and not isinstance(meta, dict):
            raise DomainError("meta must be a dict or None")
        return self.uow.transactions.ledger(
            account_full_name,
            start_dt,
            end_dt,
            meta,
            offset=offset,
            limit=limit,
            order=order_up,
        )


@dataclass
class GetTradingBalanceRawDTOs:
    """Return raw trading balance mapped to TradingBalanceLineSimple list.

    Args:
        uow: Unit of Work providing access to repositories.
        clock: Clock for default time boundaries.

    Returns:
        list[TradingBalanceLineSimple]: one line per currency, no converted fields.
    """
    uow: UnitOfWork
    clock: Clock

    def __call__(self, *, start: datetime | None = None, end: datetime | None = None, as_of: datetime | None = None) -> list[TradingBalanceLineSimple]:
        # Determine window
        win_start = start or datetime.fromtimestamp(0, tz=self.clock.now().tzinfo)
        win_end = end or as_of or self.clock.now()
        # Collect lines within window via repository
        txs = self.uow.transactions.list_between(win_start, win_end)
        # Map to domain LedgerEntry and aggregate
        dom_lines: list[LedgerEntry] = []
        for tx in txs:
            for line in tx.lines:
                side = EntrySide(line.side.upper())
                dom_lines.append(LedgerEntry(side=side.value, amount=line.amount, currency_code=line.currency_code))
        raw = RawAggregator().aggregate(dom_lines)
        # Map to DTOs
        return [
            TradingBalanceLineSimple(currency_code=item.currency_code, debit=item.debit, credit=item.credit, net=item.net)
            for item in raw
        ]


@dataclass
class GetTradingBalanceDetailedDTOs:
    """Return detailed trading balance mapped to TradingBalanceLineDetailed list.

    Args:
        uow: Unit of Work providing access to repositories.
        clock: Clock for default time boundaries.
        base currency code is required.

    Returns:
        list[TradingBalanceLineDetailed]: raw values plus *_base and used_rate.
    """
    uow: UnitOfWork
    clock: Clock

    def __call__(self, base_currency: str, *, start: datetime | None = None, end: datetime | None = None, as_of: datetime | None = None) -> list[TradingBalanceLineDetailed]:
        if not base_currency:
            raise DomainError("base_currency is required for detailed trading balance")
        # Determine window and collect
        win_start = start or datetime.fromtimestamp(0, tz=self.clock.now().tzinfo)
        win_end = end or as_of or self.clock.now()
        txs = self.uow.transactions.list_between(win_start, win_end)
        dom_lines: list[LedgerEntry] = []
        for tx in txs:
            for line in tx.lines:
                side = EntrySide(line.side.upper())
                dom_lines.append(LedgerEntry(side=side.value, amount=line.amount, currency_code=line.currency_code))
        # Build domain currency objects from repository DTOs
        all_curs = self.uow.currencies.list_all()
        from py_accountant.domain.currencies import Currency
        cur_map = { cur.code: Currency(code=cur.code, is_base=cur.is_base, rate_to_base=cur.exchange_rate) for cur in all_curs }
        # Aggregate via domain and map
        conv = ConvertedAggregator().aggregate(dom_lines, currencies=cur_map, base_code=base_currency)
        return [
            TradingBalanceLineDetailed(
                currency_code=item.currency_code,
                base_currency_code=item.base_currency_code,
                debit=item.debit,
                credit=item.credit,
                net=item.net,
                used_rate=item.used_rate,
                debit_base=item.debit_base,
                credit_base=item.credit_base,
                net_base=item.net_base,
            )
            for item in conv
        ]
