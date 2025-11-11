from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

from application.dto.models import (
    AccountDTO,
    CurrencyDTO,
    EntryLineDTO,
    RichTransactionDTO,
    TradingBalanceDTO,
    TradingBalanceLineDetailed,
    TradingBalanceLineDTO,
    TradingBalanceLineSimple,
    TransactionDTO,
)
from application.interfaces.ports import Clock, UnitOfWork
from application.utils.quantize import money_quantize
from domain import (
    AccountBalanceServiceProtocol,
    AccountName,
    CurrencyCode,
    DomainError,
    EntryLine,
    EntrySide,
    ExchangeRate,
    ExchangeRatePolicy,
    InMemoryAccountBalanceService,
    TransactionVO,
)
from domain.ledger import LedgerEntry

# New domain aggregators for DTO mapping
from domain.trading_balance import ConvertedAggregator, RawAggregator

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
class GetTradingBalance:
    uow: UnitOfWork
    clock: Clock

    def __call__(self, base_currency: str | None = None, *, start: datetime | None = None, end: datetime | None = None, as_of: datetime | None = None) -> TradingBalanceDTO:
        # Determine window and as_of
        win_start = start or datetime.fromtimestamp(0, tz=self.clock.now().tzinfo)
        win_end = end or as_of or self.clock.now()
        # Fall back to repository aggregate (as_of) when full window
        tb = self.uow.transactions.aggregate_trading_balance(as_of=win_end, base_currency=base_currency)
        # If start is specified, adjust by subtracting lines before start
        if start is not None:
            # Re-aggregate only within window using list_between
            txs = self.uow.transactions.list_between(win_start, win_end)
            from collections import defaultdict as _dd
            debit: dict[str, Decimal] = _dd(lambda: Decimal("0"))
            credit: dict[str, Decimal] = _dd(lambda: Decimal("0"))
            for tx in txs:
                for line in tx.lines:
                    if line.side.upper() == "DEBIT":
                        debit[line.currency_code] += line.amount
                    else:
                        credit[line.currency_code] += line.amount
            new_lines: list[TradingBalanceLineDTO] = []
            for cur in sorted(set(debit.keys()) | set(credit.keys())):
                d = debit.get(cur, Decimal("0"))
                c = credit.get(cur, Decimal("0"))
                new_lines.append(TradingBalanceLineDTO(currency_code=cur, total_debit=d, total_credit=c, balance=d - c))
            tb.lines = new_lines
            tb.as_of = win_end
        # Base conversion identical to previous logic
        inferred_base = base_currency
        if inferred_base is None:
            base_obj: CurrencyDTO | None = getattr(self.uow.currencies, "get_base", lambda: None)()
            if base_obj is not None:
                inferred_base = base_obj.code
        if inferred_base:
            total_base = Decimal("0")
            for line in tb.lines:
                cur_obj = self.uow.currencies.get_by_code(line.currency_code)
                if cur_obj and cur_obj.code != inferred_base and cur_obj.exchange_rate:
                    rate: Decimal = cur_obj.exchange_rate
                else:
                    rate = Decimal("1")
                zero = Decimal("0")
                line.converted_debit = money_quantize(line.total_debit / rate if rate != zero else line.total_debit)
                line.converted_credit = money_quantize(line.total_credit / rate if rate != zero else line.total_credit)
                line.converted_balance = money_quantize(line.balance / rate if rate != zero else line.balance)
                total_base += line.converted_balance  # type: ignore[arg-type]
            tb.base_currency = inferred_base
            tb.base_total = money_quantize(total_base)
        return tb


@dataclass
class GetTradingBalanceDetailed:
    uow: UnitOfWork
    clock: Clock

    def __call__(self, base_currency: str | None, *, start: datetime | None = None, end: datetime | None = None, as_of: datetime | None = None) -> TradingBalanceDTO:
        if not base_currency:
            raise DomainError("base_currency is required for detailed trading balance")
        # Reuse GetTradingBalance for windowing then recompute detailed conversion
        base = GetTradingBalance(self.uow, self.clock)(base_currency=base_currency, start=start, end=end, as_of=as_of)
        total_base = Decimal("0")
        for line in base.lines:
            cur_obj = self.uow.currencies.get_by_code(line.currency_code)
            if cur_obj and cur_obj.code != base_currency and cur_obj.exchange_rate:
                rate: Decimal = cur_obj.exchange_rate
                fallback = False
            else:
                rate = Decimal("1")
                fallback = not (cur_obj and cur_obj.code == base_currency)
            zero = Decimal("0")
            line.converted_debit = money_quantize(line.total_debit / rate if rate != zero else line.total_debit)
            line.converted_credit = money_quantize(line.total_credit / rate if rate != zero else line.total_credit)
            line.converted_balance = money_quantize(line.balance / rate if rate != zero else line.balance)
            line.rate_used = rate
            line.rate_fallback = fallback
            total_base += line.converted_balance  # type: ignore[arg-type]
        base.base_currency = base_currency
        base.base_total = money_quantize(total_base)
        return base


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
            TradingBalanceLineSimple(currency_code=l.currency_code, debit=l.debit, credit=l.credit, net=l.net)
            for l in raw
        ]


@dataclass
class GetTradingBalanceDetailedDTOs:
    """Return detailed trading balance mapped to TradingBalanceLineDetailed list.

    Args:
        uow: Unit of Work providing access to repositories.
        clock: Clock for default time boundaries.
        base_currency: Required explicit base currency code.

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
        from domain.currencies import Currency
        cur_map = { c.code: Currency(code=c.code, is_base=c.is_base, rate_to_base=c.exchange_rate) for c in all_curs }
        # Aggregate via domain and map
        conv = ConvertedAggregator().aggregate(dom_lines, currencies=cur_map, base_code=base_currency)
        return [
            TradingBalanceLineDetailed(
                currency_code=l.currency_code,
                base_currency_code=l.base_currency_code,
                debit=l.debit,
                credit=l.credit,
                net=l.net,
                used_rate=l.used_rate,
                debit_base=l.debit_base,
                credit_base=l.credit_base,
                net_base=l.net_base,
            )
            for l in conv
        ]

