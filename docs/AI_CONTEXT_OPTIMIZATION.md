# AI Context Optimization Strategy

> **Цель**: Оптимизация контекста для AI моделей при разработке/доработке кода  
> **Проблема**: Документация в docs/ предназначена для человека (10,614 строк), содержит избыточность  
> **Методология**: RPG (Repository Planning Graph)  
> **Дата**: 2025-11-28

---

## 📊 Анализ текущей ситуации

### Текущая документация (для человека)
- **Объем**: 10,614 строк в 15 файлах
- **Характер**: Подробные объяснения, примеры, tutorialы
- **Избыточность**: ~60-70% контента не нужен модели
- **Проблемы**: 
  - "Lost in the middle" эффект
  - Расход токенов на "шум"
  - Дублирование информации между файлами

### Что действительно нужно модели

1. **Контракты (Protocols)** — интерфейсы портов
2. **Data Flow** — как данные движутся между слоями
3. **DTOs структура** — какие объекты принимать/возвращать
4. **Invariants** — бизнес-правила домена
5. **Квантизация** — правила округления (money_quantize, rate_quantize)
6. **Архитектурные ограничения** — что можно/нельзя делать

---

## 🎯 Предлагаемые решения

### ✅ Вариант 1: Граф контрактов + Мини-контексты (РЕКОМЕНДУЕТСЯ)

**Принцип**: Создать дерево контрактов с минимальной семантикой для AI

#### Структура

```
ai_context/
├── contracts/
│   ├── PORTS.yaml              # Все порты с сигнатурами
│   ├── DTOS.yaml               # Все DTOs со структурой
│   ├── DOMAIN_RULES.yaml       # Инварианты домена
│   └── QUANTIZATION.yaml       # Правила округления
├── flows/
│   ├── POST_TRANSACTION.yaml   # Dataflow для PostTransaction
│   ├── GET_BALANCE.yaml        # Dataflow для GetBalance
│   └── FX_CONVERSION.yaml      # Dataflow для FX операций
├── architecture/
│   ├── LAYERS.yaml             # Структура слоев (без объяснений)
│   └── CONSTRAINTS.yaml        # Что можно/нельзя
└── INDEX.yaml                  # Навигация по контекстам
```

#### Пример: ai_context/contracts/PORTS.yaml

```yaml
# AI Context: Ports (Protocols)
# Версия: 1.1.0
# Последнее обновление: 2025-11-28

AsyncUnitOfWork:
  type: Protocol
  methods:
    - name: __aenter__
      returns: Self
    - name: __aexit__
      args: [exc_type, exc_val, exc_tb]
      returns: None
    - name: commit
      async: true
      returns: None
    - name: rollback
      async: true
      returns: None
  attributes:
    - name: accounts
      type: AsyncAccountRepository
    - name: currencies
      type: AsyncCurrencyRepository
    - name: transactions
      type: AsyncTransactionRepository
    - name: exchange_rate_events
      type: AsyncExchangeRateEventRepository

AsyncAccountRepository:
  type: Protocol
  methods:
    - name: get_by_full_name
      async: true
      args:
        - name: full_name
          type: str
      returns: Account | None
      raises:
        - ValidationError: "Invalid full_name format"
    - name: add
      async: true
      args:
        - name: account
          type: Account
      returns: None
    - name: list_all
      async: true
      returns: list[Account]

# ... другие репозитории
```

#### Пример: ai_context/flows/POST_TRANSACTION.yaml

```yaml
# AI Context: Data Flow - Post Transaction
# Use Case: AsyncPostTransaction

flow:
  - step: 1_validate_input
    action: Validate EntryLineDTO list
    rules:
      - "Sum(debits) == Sum(credits)"
      - "All amounts >= 0"
      - "All amounts quantized to 2 decimals"
  
  - step: 2_load_accounts
    action: uow.accounts.get_by_full_name()
    for_each: EntryLineDTO
    creates: Account domain objects
  
  - step: 3_create_transaction
    action: Transaction.create()
    args:
      - lines: List[EntryLine]
      - memo: str
      - posted_at: datetime
      - meta: dict
    validates:
      - Double-entry invariant
      - Account types compatibility
  
  - step: 4_persist
    action: uow.transactions.add()
    then: uow.commit()
  
  - step: 5_return
    returns: TransactionDTO

contracts_used:
  - AsyncUnitOfWork
  - AsyncAccountRepository
  - AsyncTransactionRepository
  
dtos:
  input:
    - EntryLineDTO:
        full_name: str
        debit: Decimal
        credit: Decimal
  output:
    - TransactionDTO:
        transaction_id: int
        posted_at: datetime
        memo: str
        lines: list[EntryLineDTO]

invariants:
  - "Sum debits == Sum credits"
  - "Amounts quantized (2 decimals)"
  - "No self-referencing in lines"
```

#### Преимущества варианта 1

1. **Компактность**: ~1,500-2,000 строк вместо 10,614
2. **Структурированность**: YAML легко парсить и искать
3. **Нет "шума"**: Только контракты и правила
4. **Граф зависимостей**: INDEX.yaml показывает связи
5. **Модульность**: Загружать только нужные контексты
6. **Версионность**: Каждый файл с версией

#### Размер контекста (оценка)

```
contracts/     ~600 строк  (4 файла × 150)
flows/         ~600 строк  (10 use cases × 60)
architecture/  ~300 строк  (2 файла × 150)
INDEX.yaml     ~100 строк
─────────────────────────
ИТОГО:         ~1,600 строк (85% экономия)
```

---

### ✅ Вариант 2: Контекстные карточки в RPG графе (АЛЬТЕРНАТИВА)

**Принцип**: Расширить rpg_py_accountant.yaml контрактами напрямую

#### Структура

Добавить в каждый узел RPG графа секцию `ai_context`:

```yaml
rpg:
  nodes:
    - id: N-UC-POST-TX
      name: "AsyncPostTransaction"
      type: use_case
      
      # ... существующие поля
      
      ai_context:
        contracts:
          input:
            - name: lines
              type: list[EntryLineDTO]
              schema:
                full_name: str
                debit: Decimal  # quantized(2)
                credit: Decimal # quantized(2)
            - name: memo
              type: str
            - name: meta
              type: dict | None
          output:
            type: TransactionDTO
            schema:
              transaction_id: int
              posted_at: datetime
              lines: list[EntryLineDTO]
        
        dependencies:
          - AsyncUnitOfWork.transactions
          - AsyncUnitOfWork.accounts
        
        invariants:
          - "sum(line.debit for line in lines) == sum(line.credit for line in lines)"
          - "all(line.debit >= 0 and line.credit >= 0 for line in lines)"
        
        dataflow:
          - "1. Validate lines (double-entry)"
          - "2. Load accounts by full_name"
          - "3. Create Transaction domain object"
          - "4. Persist via uow.transactions.add()"
          - "5. Commit UoW"
          - "6. Return TransactionDTO"
```

#### Преимущества варианта 2

1. **Единый источник истины**: Все в rpg_py_accountant.yaml
2. **Граф + контракты**: Зависимости уже есть
3. **Топологический порядок**: Модель видит порядок реализации
4. **Интеграция с RPG**: Не нужен отдельный инструментарий

#### Недостатки варианта 2

1. **Размер**: rpg_py_accountant.yaml станет больше (~3,000+ строк)
2. **Сложность поиска**: Нужно парсить граф
3. **Ограниченность**: Сложно выразить сложные flows

---

### ✅ Вариант 3: AI-оптимизированная документация (ГИБРИД)

**Принцип**: Параллельная документация для AI с форматом JSON-Schema + примерами

#### Структура

```
ai_docs/
├── contracts.json         # JSON-Schema для всех портов/DTOs
├── flows.json             # Dataflows в виде directed graphs
├── rules.json             # Инварианты и ограничения
└── examples_minimal.json  # Только code snippets без объяснений
```

#### Пример: ai_docs/contracts.json

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "version": "1.1.0",
  "updated": "2025-11-28",
  
  "protocols": {
    "AsyncUnitOfWork": {
      "type": "Protocol",
      "methods": [
        {
          "name": "__aenter__",
          "async": true,
          "returns": "Self"
        },
        {
          "name": "commit",
          "async": true,
          "returns": "None",
          "raises": []
        }
      ],
      "attributes": [
        {"name": "accounts", "type": "AsyncAccountRepository"},
        {"name": "currencies", "type": "AsyncCurrencyRepository"}
      ]
    }
  },
  
  "dtos": {
    "EntryLineDTO": {
      "$ref": "#/definitions/EntryLineDTO"
    }
  },
  
  "definitions": {
    "EntryLineDTO": {
      "type": "object",
      "properties": {
        "full_name": {"type": "string", "pattern": "^[A-Z0-9]+:[A-Z0-9_]+$"},
        "debit": {"type": "string", "format": "decimal", "precision": 2},
        "credit": {"type": "string", "format": "decimal", "precision": 2}
      },
      "required": ["full_name", "debit", "credit"]
    }
  }
}
```

#### Преимущества варианта 3

1. **JSON-Schema**: Стандарт, легко валидировать
2. **Компактность**: ~2,000 строк (4 файла)
3. **Машиночитаемость**: AI может парсить schema
4. **Интеграция с IDE**: JSON-Schema поддерживается везде

#### Недостатки варианта 3

1. **Дублирование**: Нужно поддерживать синхронность
2. **JSON не выразителен**: Сложные flows читаются хуже

---

### ✅ Вариант 4: Автогенерация из кода (АВТОМАТИЗАЦИЯ)

**Принцип**: Генерировать AI-контексты из исходного кода + docstrings

#### Инструментарий

```python
# tools/generate_ai_context.py

class AIContextGenerator:
    """Generate AI-optimized context from source code."""
    
    def extract_protocols(self, module_path: str) -> dict:
        """Extract all Protocol classes with methods."""
        # Parse AST → extract Protocol classes → signatures
        
    def extract_dtos(self, module_path: str) -> dict:
        """Extract all dataclass DTOs."""
        # Parse dataclasses → extract fields + types
    
    def extract_flows(self, use_case_path: str) -> dict:
        """Extract dataflow from use case docstring."""
        # Parse structured docstring → build flow graph
    
    def generate_yaml(self, output_dir: Path) -> None:
        """Generate ai_context/ directory."""
```

#### Структура docstring для автогенерации

```python
@dataclass(slots=True)
class AsyncPostTransaction:
    """Post a transaction to the ledger.
    
    AI_CONTEXT:
        flow:
            - step: validate_input
              action: Check double-entry invariant
              rules: [sum(debits) == sum(credits)]
            - step: load_accounts
              action: uow.accounts.get_by_full_name()
            - step: create_transaction
              action: Transaction.create()
            - step: persist
              action: uow.transactions.add() → uow.commit()
        
        invariants:
            - Double-entry: sum(debits) == sum(credits)
            - Quantization: All amounts 2 decimals
    """
    
    uow: AsyncUnitOfWork
    clock: Clock
    
    async def __call__(self, lines: list[EntryLineDTO], ...) -> TransactionDTO:
        """Execute the use case."""
```

#### Преимущества варианта 4

1. **Актуальность**: Генерируется из кода → нет расхождений
2. **Автоматизация**: CI/CD генерирует при каждом коммите
3. **Минимум ручной работы**: Только docstrings
4. **Интеграция с RPG**: Может генерировать ai_context в rpg.yaml

#### Недостатки варианта 4

1. **Сложность**: Нужен парсер AST
2. **Зависимость от структуры**: Изменение кода → изменение парсера
3. **Docstring дисциплина**: Требует строгих конвенций

---

## 🎯 Рекомендация: Комбинированный подход

### Оптимальная стратегия

**Фаза 1: Ручная (быстрый старт)**  
✅ Вариант 1 - Создать ai_context/ вручную для core контрактов

**Фаза 2: Расширение**  
✅ Вариант 2 - Добавить ai_context в RPG граф для новых узлов

**Фаза 3: Автоматизация**  
✅ Вариант 4 - Автогенерация из docstrings для синхронизации

### Конкретный план

```yaml
# План реализации
phases:
  - phase: 1_manual_bootstrap
    duration: 2 hours
    tasks:
      - Создать ai_context/contracts/PORTS.yaml (core 5 protocols)
      - Создать ai_context/contracts/DTOS.yaml (top 10 DTOs)
      - Создать ai_context/contracts/DOMAIN_RULES.yaml
      - Создать ai_context/flows/ (top 5 use cases)
      - Создать ai_context/INDEX.yaml
    
  - phase: 2_rpg_integration
    duration: 3 hours
    tasks:
      - Добавить ai_context секцию в rpg_py_accountant.yaml
      - Заполнить для всех use cases узлов
      - Обновить tools/rpg/yaml_writer.py для поддержки ai_context
    
  - phase: 3_automation
    duration: 5 hours
    tasks:
      - Создать tools/generate_ai_context.py
      - Добавить AI_CONTEXT секцию в docstrings
      - Настроить CI/CD генерацию
      - Валидация синхронности
```

---

## 📏 Метрики эффективности

### Ожидаемые результаты

| Метрика | Текущее | После оптимизации | Улучшение |
|---------|---------|-------------------|-----------|
| Контекст для модели | 10,614 строк | ~1,600 строк | **85% ↓** |
| Токенов на запрос | ~40,000 | ~6,000 | **85% ↓** |
| "Lost in middle" эффект | Высокий | Минимальный | **90% ↓** |
| Актуальность | Ручная | Автосинхронизация | **100% ↑** |
| Время поиска контракта | ~30 сек | ~5 сек | **83% ↓** |

### Целевые показатели

- **Контекст**: < 2,000 строк на полный проект
- **Точность**: 95%+ для контрактов
- **Актуальность**: 100% синхронность с кодом
- **Модульность**: Загрузка только нужных контекстов

---

## 🔧 Пример использования

### Для модели при разработке нового use case

```yaml
# Запрос модели: "Implement AsyncCreateAccount use case"

# 1. Загрузить контракты
ai_context/contracts/PORTS.yaml:
  - AsyncUnitOfWork
  - AsyncAccountRepository

ai_context/contracts/DTOS.yaml:
  - AccountDTO

ai_context/contracts/DOMAIN_RULES.yaml:
  - Account validation rules

# 2. Посмотреть похожий flow
ai_context/flows/CREATE_CURRENCY.yaml

# 3. Проверить архитектурные ограничения
ai_context/architecture/CONSTRAINTS.yaml

# Итого: ~300 строк контекста вместо 10,614
```

---

## 🚀 Следующие шаги

1. **Выбрать вариант** (рекомендуется Комбинированный)
2. **Создать структуру** ai_context/
3. **Заполнить core контракты** (2 часа)
4. **Протестировать** с реальной моделью
5. **Автоматизировать** генерацию (фаза 3)

---

## Приложение: Сравнительная таблица

| Критерий | Вариант 1 | Вариант 2 | Вариант 3 | Вариант 4 |
|----------|-----------|-----------|-----------|-----------|
| Компактность | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Актуальность | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| Читаемость | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| Простота внедрения | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ |
| Интеграция с RPG | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ |
| Автоматизация | ⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ |

**Рекомендация**: Комбинировать Вариант 1 (быстрый старт) → Вариант 2 (интеграция) → Вариант 4 (автоматизация)

