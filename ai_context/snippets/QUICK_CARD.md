# Quick Reference Card - py_accountant

> Копируй эту карточку в промпт для быстрого старта

```markdown
## py_accountant Quick Ref

**Architecture**: Ports & Adapters | **Version**: 1.1.0 | **Async-only**

### Use Case Pattern
```python
@dataclass(slots=True)
class AsyncSomeUseCase:
    uow: AsyncUnitOfWork
    async def __call__(self, ...) -> DTO:
        async with self.uow:
            # validate → load → create domain → persist → commit → return DTO
            await self.uow.commit()
            return DTO(...)
```

### Key Ports
```python
AsyncUnitOfWork: accounts, currencies, transactions, exchange_rate_events
AsyncAccountRepository: get_by_full_name(), add(), list_all()
```

### Quantization (CRITICAL!)
```python
from py_accountant.domain.quantize import money_quantize, rate_quantize
amount = money_quantize(Decimal("100.123"))  # → 100.12 (2 decimals)
rate = rate_quantize(Decimal("1.234567"))    # → 1.234567 (6 decimals)
```

### Invariants
- **Double-entry**: sum(debits) == sum(credits)
- **Account format**: "TYPE:NAME" (e.g., "ASSET:CASH_USD")
- **Amounts**: >= 0, quantized to 2 decimals
- **Repos**: CRUD-only, return domain objects, return None (not raise)

### Rules
- ✓ Use Decimal (NEVER float)
- ✓ Quantize after arithmetic, before persistence
- ✓ Async use cases with UoW transaction
- ✓ Business logic in domain (not use case)
- ✗ Don't import infrastructure in application

### Common DTOs
- **EntryLineDTO**: full_name, debit, credit
- **TransactionDTO**: transaction_id, posted_at, memo, lines, meta
- **AccountDTO**: full_name, account_type, name, currency_code, metadata
```

