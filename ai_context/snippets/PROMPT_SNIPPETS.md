# AI Context Prompt Snippets

> **Цель**: Готовые сниппеты для вставки в промпты при разработке/доработке кода  
> **Использование**: Копируй нужный сниппет в свой промпт для AI модели  
> **Версия**: 1.1.0  
> **Дата**: 2025-11-28

---

## 📋 Оглавление

1. [Базовая архитектура](#snippet-1-базовая-архитектура)
2. [Контракты портов](#snippet-2-контракты-портов)
3. [Основные DTOs](#snippet-3-основные-dtos)
4. [Квантизация](#snippet-4-квантизация)
5. [Инварианты домена](#snippet-5-инварианты-домена)
6. [Паттерн use case](#snippet-6-паттерн-use-case)
7. [Data flow template](#snippet-7-data-flow-template)
8. [Архитектурные ограничения](#snippet-8-архитектурные-ограничения)
9. [Типичные ошибки](#snippet-9-типичные-ошибки)
10. [Полный контекст](#snippet-10-полный-контекст)

---

## Snippet 1: Базовая архитектура

**Когда использовать**: При любой разработке, для понимания общей структуры

```markdown
## Architecture Context

**py_accountant** - async-first бухгалтерская система
- Архитектура: Ports & Adapters (Hexagonal)
- Слои: Domain (чистый) → Application (use cases) → Infrastructure (I/O)
- Правило: Domain не зависит от Application/Infrastructure
- Async только: все use cases и repositories async
- Версия: 1.1.0 | Schema: 0008_add_account_aggregates

**Dependency Rule**:
```
Infrastructure → Application → Domain
           ↓           ↓
    (implements)  (defines ports)
```
```

**Размер**: ~15 строк

---

## Snippet 2: Контракты портов

**Когда использовать**: При создании/модификации use cases

```markdown
## Ports (Protocols)

### AsyncUnitOfWork
```python
class AsyncUnitOfWork(Protocol):
    accounts: AsyncAccountRepository
    currencies: AsyncCurrencyRepository
    transactions: AsyncTransactionRepository
    exchange_rate_events: AsyncExchangeRateEventRepository
    
    async def __aenter__(self) -> Self: ...
    async def __aexit__(self, ...): ...
    async def commit(self): ...
    async def rollback(self): ...
```

### AsyncAccountRepository
```python
class AsyncAccountRepository(Protocol):
    async def get_by_full_name(self, full_name: str) -> Account | None: ...
    async def add(self, account: Account) -> None: ...
    async def list_all(self) -> list[Account]: ...
    async def get_balances(self, as_of: datetime | None = None) -> dict: ...
```

**Rule**: CRUD-only, return domain objects (not DTOs), return None (not raise)
```

**Размер**: ~25 строк

---

## Snippet 3: Основные DTOs

**Когда использовать**: При работе с входами/выходами use cases

```markdown
## Core DTOs

### EntryLineDTO (input for transactions)
```python
@dataclass
class EntryLineDTO:
    full_name: str        # "ASSET:CASH_USD"
    debit: Decimal        # quantized to 2 decimals
    credit: Decimal       # quantized to 2 decimals
```

### TransactionDTO (output)
```python
@dataclass
class TransactionDTO:
    transaction_id: int
    posted_at: datetime   # UTC
    memo: str
    lines: list[EntryLineDTO]
    meta: dict | None
```

### AccountDTO
```python
@dataclass
class AccountDTO:
    full_name: str        # "TYPE:NAME"
    account_type: str     # ASSET|LIABILITY|EQUITY|REVENUE|EXPENSE
    name: str
    currency_code: str
    metadata: dict | None
```

**Serialization**: Decimal → string, datetime → ISO8601 UTC, keys → snake_case
```

**Размер**: ~35 строк

---

## Snippet 4: Квантизация

**Когда использовать**: При работе с Decimal (всегда!)

```markdown
## Quantization Rules

**CRITICAL**: All Decimal values MUST be quantized

```python
from py_accountant.domain.quantize import money_quantize, rate_quantize
from decimal import Decimal

# Money (2 decimals, ROUND_HALF_EVEN)
amount = money_quantize(Decimal("100.123"))  # → 100.12

# Rates (6 decimals, ROUND_HALF_EVEN)
rate = rate_quantize(Decimal("1.234567"))    # → 1.234567

# FX conversion
amount_base = money_quantize(amount * rate)  # → 2 decimals
```

**Rules**:
- ✓ Quantize AFTER arithmetic, BEFORE persistence
- ✓ Use Decimal, NEVER float
- ✗ Don't quantize intermediate steps (preserve precision)

**Why ROUND_HALF_EVEN**: Banker's rounding reduces bias
```

**Размер**: ~25 строк

---

## Snippet 5: Инварианты домена

**Когда использовать**: При реализации бизнес-логики

```markdown
## Domain Invariants

### Double-Entry (CRITICAL)
```python
# sum(debits) == sum(credits)
total_debit = sum(line.debit for line in lines)
total_credit = sum(line.credit for line in lines)
if total_debit != total_credit:
    raise ValidationError("Transaction does not balance")
```

### Account Validation
- full_name pattern: `^[A-Z0-9]+:[A-Z0-9_]+$` (e.g., "ASSET:CASH_USD")
- account_type: ASSET | LIABILITY | EQUITY | REVENUE | EXPENSE
- currency_code must exist

### Transaction Rules
- Minimum 2 lines
- debit >= 0 AND credit >= 0
- NOT (debit > 0 AND credit > 0) - one side must be zero
- All amounts quantized to 2 decimals

### FX Conversion
- Base currency: rate = 1.0 (always)
- Non-base: rate > 0 (must exist)
- Conversion: amount_base = money_quantize(amount * rate)
```

**Размер**: ~30 строк

---

## Snippet 6: Паттерн use case

**Когда использовать**: При создании нового use case

```markdown
## Use Case Pattern

```python
from dataclasses import dataclass
from py_accountant.application.ports import AsyncUnitOfWork
from py_accountant.application.dto import SomeDTO

@dataclass(slots=True)
class AsyncSomeUseCase:
    """Use case description.
    
    Args:
        param1: Description
        param2: Description
    
    Returns:
        ResultDTO
    
    Raises:
        ValidationError: When domain invariant violated
        ValueError: When resource not found
    """
    
    uow: AsyncUnitOfWork  # Dependency injection
    # other dependencies (Clock, etc.)
    
    async def __call__(self, param1: Type1, param2: Type2) -> ResultDTO:
        """Execute the use case."""
        async with self.uow:
            # 1. Load dependencies from UoW
            entity = await self.uow.some_repo.get_by_id(param1)
            if entity is None:
                raise ValueError(f"Not found: {param1}")
            
            # 2. Validate input
            # 3. Create/modify domain objects
            # 4. Persist via repositories
            await self.uow.some_repo.add(entity)
            
            # 5. Commit UoW
            await self.uow.commit()
            
            # 6. Return DTO
            return ResultDTO(...)
```

**Rules**:
- ✓ Async only
- ✓ Dependencies via constructor (DI)
- ✓ Use UoW for transaction boundary
- ✓ Convert: DTO → Domain → DTO
- ✗ No business logic in use case (delegate to domain)
```

**Размер**: ~55 строк

---

## Snippet 7: Data Flow Template

**Когда использовать**: Для понимания потока данных конкретного use case

```markdown
## Data Flow: [Use Case Name]

**Steps**:
1. **Validate input** - Check DTO structure and invariants
2. **Load dependencies** - `await uow.repo.get_by_*()`
3. **Create domain objects** - `Entity.create()` with validation
4. **Persist** - `await uow.repo.add(entity)`
5. **Commit** - `await uow.commit()`
6. **Return DTO** - Convert domain → DTO

**Example**: AsyncPostTransaction
```python
# 1. Validate
if sum(line.debit) != sum(line.credit):
    raise ValidationError("Unbalanced")

# 2. Load accounts
accounts = []
for line in lines:
    acc = await uow.accounts.get_by_full_name(line.full_name)
    if acc is None:
        raise ValueError(f"Account not found: {line.full_name}")
    accounts.append(acc)

# 3. Create transaction
transaction = Transaction.create(
    lines=[EntryLine(...) for ...],
    memo=memo,
    posted_at=clock.now(),
)

# 4-5. Persist and commit
await uow.transactions.add(transaction)
await uow.commit()

# 6. Return DTO
return TransactionDTO(...)
```
```

**Размер**: ~45 строк

---

## Snippet 8: Архитектурные ограничения

**Когда использовать**: Для проверки правильности дизайна

```markdown
## Architecture Constraints

### Layer Rules

**Domain** (py_accountant.domain)
- ✓ CAN: Pure functions, validate invariants, raise DomainError/ValidationError
- ✗ CANNOT: I/O, async/await, import from application/infrastructure

**Application** (py_accountant.application)
- ✓ CAN: Orchestrate domain, use repos via ports, async/await, convert DTOs
- ✗ CANNOT: Implement repos, import from infrastructure, business logic

**Infrastructure** (py_accountant.infrastructure)
- ✓ CAN: Implement repos, DB I/O, import from application/domain
- ✗ CANNOT: Business logic (delegate to domain)

### Repository Rules
- CRUD-only (no business logic)
- Return domain objects (not DTOs)
- Return None for not found (don't raise)
- Raise ValidationError on invalid input

### Use Case Rules
- Async only
- Dependency injection via constructor
- Use UoW for transaction boundary
- No business logic (orchestrate domain instead)

### Import Rules
```python
# ✓ ALLOWED
from py_accountant.application.ports import AsyncUnitOfWork
from py_accountant.domain.account import Account

# ✗ FORBIDDEN in application layer
from py_accountant.infrastructure.persistence import SqlAlchemyRepo
```
```

**Размер**: ~40 строк

---

## Snippet 9: Типичные ошибки

**Когда использовать**: Для избежания распространенных проблем

```markdown
## Common Mistakes

### ❌ Using float instead of Decimal
```python
# BAD
amount = 100.12  # float has precision errors

# GOOD
amount = Decimal("100.12")
```

### ❌ Forgetting to quantize
```python
# BAD
total = amount1 + amount2  # might have 3+ decimals

# GOOD
total = money_quantize(amount1 + amount2)
```

### ❌ Business logic in use case
```python
# BAD - validation in use case
if amount < 0:
    raise ValidationError("Negative amount")

# GOOD - validation in domain
validated_amount = Money.create(amount)  # domain validates
```

### ❌ Not using UoW transaction
```python
# BAD
account = await repo.get_by_id(id)
await repo.add(account)
# No commit!

# GOOD
async with uow:
    account = await uow.accounts.get_by_id(id)
    await uow.accounts.add(account)
    await uow.commit()
```

### ❌ Wrong imports
```python
# BAD - importing infrastructure in application
from infrastructure.persistence import SqlAlchemyRepo

# GOOD - using ports
from application.ports import AsyncAccountRepository
```
```

**Размер**: ~50 строк

---

## Snippet 10: Полный контекст

**Когда использовать**: Для сложных задач, требующих максимального контекста

```markdown
## Full Context: py_accountant Development

### Architecture
- **Style**: Ports & Adapters (Hexagonal)
- **Layers**: Domain → Application → Infrastructure
- **Async**: Use cases and repos are async-only
- **Version**: 1.1.0 | Schema: 0008_add_account_aggregates

### Core Ports
```python
class AsyncUnitOfWork(Protocol):
    accounts: AsyncAccountRepository
    currencies: AsyncCurrencyRepository
    transactions: AsyncTransactionRepository
    exchange_rate_events: AsyncExchangeRateEventRepository
    async def commit(self): ...
    async def rollback(self): ...
```

### Core DTOs
- **EntryLineDTO**: full_name, debit, credit (all Decimal quantized to 2)
- **TransactionDTO**: transaction_id, posted_at, memo, lines, meta
- **AccountDTO**: full_name, account_type, name, currency_code, metadata

### Critical Rules
1. **Quantization**: 
   - Money: 2 decimals (money_quantize)
   - Rates: 6 decimals (rate_quantize)
   - Rounding: ROUND_HALF_EVEN

2. **Double-Entry**: sum(debits) == sum(credits)

3. **Account Format**: "TYPE:NAME" where TYPE in [ASSET, LIABILITY, EQUITY, REVENUE, EXPENSE]

4. **Repositories**: CRUD-only, return domain objects, return None (not raise)

5. **Use Cases**: 
   - Pattern: validate → load → create domain → persist → commit → return DTO
   - Async with UoW transaction boundary
   - No business logic (delegate to domain)

6. **Layer Constraints**:
   - Domain: No I/O, no async, no imports from app/infra
   - Application: No infra imports, use ports
   - Infrastructure: Implements ports

### Use Case Template
```python
@dataclass(slots=True)
class AsyncSomeUseCase:
    uow: AsyncUnitOfWork
    
    async def __call__(self, param: Type) -> ResultDTO:
        async with self.uow:
            # 1. Validate, 2. Load, 3. Create domain
            # 4. Persist, 5. Commit, 6. Return DTO
            await self.uow.commit()
            return ResultDTO(...)
```

### Common Patterns
```python
# Quantization
from py_accountant.domain.quantize import money_quantize
amount = money_quantize(Decimal("100.123"))  # → 100.12

# Loading account
account = await uow.accounts.get_by_full_name("ASSET:CASH_USD")
if account is None:
    raise ValueError("Account not found")

# Creating transaction
transaction = Transaction.create(lines=[...], memo="...", posted_at=clock.now())
```

### Avoid
- ❌ float (use Decimal)
- ❌ Forgetting quantization
- ❌ Business logic in use case
- ❌ Direct infra imports in application
- ❌ Not using UoW transaction
```

**Размер**: ~90 строк

---

## 🎯 Как использовать сниппеты

### Сценарий 1: Создание нового use case

**Промпт**:
```
Implement AsyncCreateAccount use case for py_accountant.

[Вставить Snippet 1: Базовая архитектура]
[Вставить Snippet 2: Контракты портов]
[Вставить Snippet 3: Основные DTOs]
[Вставить Snippet 5: Инварианты домена]
[Вставить Snippet 6: Паттерн use case]

Requirements:
- Create account with full_name and currency_code
- Validate full_name format
- Check currency exists
- Return AccountDTO
```

**Контекст**: ~150 строк вместо 10,614 в docs/

---

### Сценарий 2: Доработка существующего кода

**Промпт**:
```
Modify AsyncPostTransaction to support multi-currency transactions.

[Вставить Snippet 4: Квантизация]
[Вставить Snippet 5: Инварианты домена (FX Conversion)]
[Вставить Snippet 7: Data Flow Template]

Current implementation:
[код]

Add FX conversion using latest exchange rates.
```

**Контекст**: ~100 строк

---

### Сценарий 3: Исправление ошибки

**Промпт**:
```
Fix ValidationError in transaction creation.

[Вставить Snippet 5: Инварианты домена]
[Вставить Snippet 9: Типичные ошибки]

Error: "Transaction does not balance"
Code: [код с ошибкой]
```

**Контекст**: ~80 строк

---

### Сценарий 4: Архитектурный ревью

**Промпт**:
```
Review this code for architecture violations.

[Вставить Snippet 8: Архитектурные ограничения]

Code to review:
[код]
```

**Контекст**: ~40 строк

---

### Сценарий 5: Полная разработка (сложная задача)

**Промпт**:
```
Implement complete trading balance feature with FX conversion.

[Вставить Snippet 10: Полный контекст]

Requirements:
- Aggregate ASSET accounts by currency
- Convert to base currency using latest rates
- Return TradingBalanceDetailedDTO
```

**Контекст**: ~90 строк

---

## 📦 Экспорт сниппетов

### Для IDE (VS Code, PyCharm)

Сниппеты можно добавить в:
- VS Code: `.vscode/snippets.code-snippets`
- PyCharm: Settings → Live Templates

### Для командной строки

```bash
# Вывести конкретный сниппет
grep -A 50 "## Snippet 6" ai_context/snippets/PROMPT_SNIPPETS.md

# Скопировать в буфер (macOS)
grep -A 50 "## Snippet 6" ai_context/snippets/PROMPT_SNIPPETS.md | pbcopy
```

---

## 📊 Сравнение размеров контекста

| Сценарий | Традиционный docs/ | Со сниппетами | Экономия |
|----------|-------------------|---------------|----------|
| Новый use case | 10,614 строк | ~150 строк | **98.6%** |
| Доработка кода | 10,614 строк | ~100 строк | **99.1%** |
| Исправление ошибки | 10,614 строк | ~80 строк | **99.2%** |
| Архитектурный ревью | 10,614 строк | ~40 строк | **99.6%** |
| Полная разработка | 10,614 строк | ~90 строк | **99.2%** |

**Среднее**: **99.1% экономия контекста**

---

## 🔗 См. также

- **ai_context/INDEX.yaml** - полная навигация по контекстам
- **ai_context/README.md** - руководство пользователя
- **ai_context/VALIDATION_REPORT.md** - отчет валидации YAML
- **docs/AI_CONTEXT_OPTIMIZATION.md** - стратегия оптимизации

---

**Последнее обновление**: 2025-11-28  
**Версия**: 1.0  
**Статус**: Production Ready ✅

