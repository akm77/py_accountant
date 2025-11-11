from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from application.dto.models import (
    AccountDTO,
    CurrencyDTO,
    EntryLineDTO,
    TradingBalanceDTO,
    TradingBalanceLineDetailed,
    TradingBalanceLineSimple,
    TransactionDTO,
)
from application.interfaces.ports import (
    AccountRepository,
    Clock,
    CurrencyRepository,
    TransactionRepository,
)


def test_dto_shapes() -> None:
    cur = CurrencyDTO(code="USD", name="US Dollar", precision=2)
    acc = AccountDTO(id="1", name="Cash", full_name="Assets:Cash", currency_code="USD")
    line = EntryLineDTO(side="DEBIT", account_full_name="Assets:Cash", amount=Decimal("10.00"), currency_code="USD")
    tx = TransactionDTO(id="t1", occurred_at=datetime.now(UTC), lines=[line])
    tline_raw = TradingBalanceLineSimple(currency_code="USD", debit=Decimal("10"), credit=Decimal("0"), net=Decimal("10"))
    tline_det = TradingBalanceLineDetailed(currency_code="USD", base_currency_code="USD", debit=Decimal("10"), credit=Decimal("0"), net=Decimal("10"), used_rate=Decimal("1"), debit_base=Decimal("10"), credit_base=Decimal("0"), net_base=Decimal("10"))
    bal = TradingBalanceDTO(as_of=datetime.now(UTC), lines=[], base_currency="USD")

    assert cur.code == "USD"
    assert acc.full_name.startswith("Assets")
    assert tx.lines[0].amount == Decimal("10.00")
    assert tline_raw.net == Decimal("10")
    assert tline_det.net_base == Decimal("10")
    assert bal.base_currency == "USD"


def test_ports_protocols() -> None:
    # Dummy implementations satisfy Protocols
    class DummyClock:
        def now(self):  # type: ignore[override]
            return datetime.now(UTC)

    class DummyCur:
        def get_by_code(self, code: str): ...
        def upsert(self, dto: CurrencyDTO): ...
        def list_all(self): ...
        def get_base(self): ...
        def set_base(self, code: str): ...
        def clear_base(self): ...
        def bulk_upsert_rates(self, updates): ...

    class DummyAcc:
        def get_by_full_name(self, full_name: str): ...
        def create(self, dto: AccountDTO): ...
        def list(self, parent_id: str | None = None): ...

    class DummyTx:
        def add(self, dto: TransactionDTO): ...
        def list_between(self, start: datetime, end: datetime, meta: dict | None = None): ...
        def aggregate_trading_balance(self, as_of: datetime, base_currency: str | None = None): ...
        def ledger(self, account_full_name: str, start: datetime, end: datetime, meta: dict | None = None, *, offset: int = 0, limit: int | None = None, order: str = "ASC"): ...
        def account_balance(self, account_full_name: str, as_of: datetime): ...

    assert isinstance(DummyClock(), Clock)
    assert isinstance(DummyCur(), CurrencyRepository)
    assert isinstance(DummyAcc(), AccountRepository)
    assert isinstance(DummyTx(), TransactionRepository)
