// ...existing code...
```python
from infrastructure.persistence.sqlalchemy.uow import SqlAlchemyUnitOfWork
from application.use_cases.ledger import CreateCurrency, CreateAccount, PostTransaction, GetBalance, GetTradingBalance
from application.dto.models import EntryLineDTO
from datetime import timezone, datetime
from dataclasses import dataclass
from decimal import Decimal

@dataclass
class SystemClock:
    tz = timezone.utc
    def now(self) -> datetime:
        return datetime.now(self.tz)

clock = SystemClock()

db_url = "sqlite+pysqlite:///./example.db"
uow = SqlAlchemyUnitOfWork(db_url)

# 1. Создать базовую валюту
CreateCurrency(uow)("USD", exchange_rate=Decimal("1"))
uow.currencies.set_base("USD")
# 2. Создать счёт
CreateAccount(uow)("Assets:Cash", "USD")
# 3. Провести транзакцию
lines = [
    EntryLineDTO(side="DEBIT", account_full_name="Assets:Cash", amount=Decimal("100"), currency_code="USD"),
    EntryLineDTO(side="CREDIT", account_full_name="Income:Sales", amount=Decimal("100"), currency_code="USD"),
]
PostTransaction(uow, clock)(lines, memo="Init balance")
# 4. Коммит
uow.commit()
# 5. Баланс
balance = GetBalance(uow, clock)("Assets:Cash")
print("Balance=", balance)
# 6. Trading balance (агрегат по валютам)
trading = GetTradingBalance(uow, clock)(base_currency="USD")
print(trading.base_total)
```
// ...existing code...
```python
from decimal import Decimal
CreateCurrency(uow)("EUR", exchange_rate=Decimal("1.1234"))
```
// ...existing code...
```python
from decimal import Decimal
from application.dto.models import EntryLineDTO
lines = [
    EntryLineDTO("DEBIT", "Assets:Cash", amount=Decimal("150"), currency_code="USD"),
    EntryLineDTO("CREDIT", "Income:Sales", amount=Decimal("150"), currency_code="USD"),
]
PostTransaction(uow, clock)(lines, memo="Sale #42")
uow.commit()
```
// ...existing code...
```python
from application.use_cases.ledger import GetTradingBalanceDetailed
GetTradingBalanceDetailed(uow, clock)(base_currency="USD")
```
// ...existing code...
```python
from infrastructure.persistence.sqlalchemy.uow import SqlAlchemyUnitOfWork
from application.use_cases.exchange_rates import UpdateExchangeRates
from application.dto.models import RateUpdateInput
from decimal import Decimal

uow = SqlAlchemyUnitOfWork(db_url)
try:
    UpdateExchangeRates(uow)([RateUpdateInput(code="EUR", rate=Decimal("1.12"))])
    uow.commit()
except Exception:
    uow.rollback()
    raise
```
// ...existing code...
