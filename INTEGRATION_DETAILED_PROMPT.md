commit# Промпт: Детальное руководство по интеграции py_accountant

## Задача

Расширить документ `docs/INTEGRATION_GUIDE.md`, добавив **ОЧЕНЬ ПОДРОБНОЕ** пошаговое руководство по интеграции пакета `py_accountant` в сторонние проекты. Основной фокус — интеграция в телеграм-бот на фреймворке **aiogram** (v3.x).

---

## Требования к новому разделу

### 1. Целевая аудитория
- Разработчики, интегрирующие `py_accountant` в существующий проект
- Уровень: middle+ (знание Python, async/await, базовые знания SQLAlchemy и aiogram)
- Предполагается, что читатель знаком с Clean Architecture на уровне концепции

### 2. Структура нового раздела (добавить после существующего содержимого)

```markdown
## Детальный пример интеграции: Telegram Bot на aiogram

### Введение
[Краткое описание сценария: телеграм-бот для управления личными финансами]

### Архитектура интеграции
[Диаграмма слоёв: Bot Layer → Adapter Layer → py_accountant Core]

### Шаг 1: Подготовка проекта
- Структура директорий
- pyproject.toml с зависимостями
- .env конфигурация (dual-URL стратегия)

### Шаг 2: Реализация UnitOfWork адаптера
- Наследование от AsyncSqlAlchemyUnitOfWork
- Или custom wrapper (если нужна дополнительная логика)
- Конфигурация engine pool settings для aiogram
- Lifecycle management (on_startup/on_shutdown)

### Шаг 3: Реализация Clock адаптера
- SystemClock vs FixedClock (для тестов)
- Интеграция с timezone bot users

### Шаг 4: Маппинг bot команд → use cases
- /deposit → PostTransaction use case
- /balance → AsyncGetAccountBalance use case
- /history → AsyncListLedger use case
- /rates → AsyncListCurrencies use case

### Шаг 5: Dependency Injection
- aiogram middlewares для UoW и Clock
- Context vars для transaction boundaries
- Graceful shutdown и cleanup

### Шаг 6: Обработка ошибок
- DomainError → пользовательские сообщения
- ValidationError → подсказки пользователю
- DB errors → логирование и fallback

### Шаг 7: Миграции в production
- Alembic в CI/CD pipeline
- Стратегия zero-downtime deployment
- Rollback процедуры

### Шаг 8: Логирование
- Отключение py_accountant.logging (LOGGING_ENABLED=false)
- Интеграция с bot logger (aiogram + structlog)
- Correlation IDs (user_id, chat_id)

### Шаг 9: Тестирование
- Unit-тесты bot handlers (mocked UoW)
- Integration тесты (InMemoryUnitOfWork)
- E2E тесты (test database)

### Шаг 10: Production checklist
- Environment variables
- Database pool tuning
- Monitoring и alerts
- Backup стратегия
```

---

## Детальные требования к каждому шагу

### Шаг 1: Подготовка проекта

**Что включить:**
- Полная структура директорий (tree view)
- Пример `pyproject.toml` с версиями:
  - aiogram >= 3.0
  - py_accountant (git dependency)
  - python-dotenv
  - structlog (опционально)
- Пример `.env` файла с комментариями:
  ```
  # Bot config
  BOT_TOKEN=...
  
  # py_accountant: sync URL for migrations
  PYACC__DATABASE_URL=postgresql+psycopg://...
  
  # py_accountant: async URL for runtime
  PYACC__DATABASE_URL_ASYNC=postgresql+asyncpg://...
  
  # Disable py_accountant logging (we use bot logger)
  PYACC__LOGGING_ENABLED=false
  
  # Pool settings for aiogram workload
  PYACC__DB_POOL_SIZE=20
  PYACC__DB_MAX_OVERFLOW=10
  ```

### Шаг 2: Реализация UnitOfWork адаптера

**Что включить:**
- Полный код класса `BotUnitOfWork` или использование `AsyncSqlAlchemyUnitOfWork`
- Объяснение выбора: когда использовать встроенный, когда писать свой
- Пример инициализации в bot startup:
  ```python
  from py_accountant.infrastructure.persistence.sqlalchemy.uow import AsyncSqlAlchemyUnitOfWork
  
  async def on_startup(bot: Bot):
      # Создание UoW factory
      uow_factory = lambda: AsyncSqlAlchemyUnitOfWork(
          url=settings.database_url_async,
          echo=settings.db_echo
      )
      # Сохранение в bot data для доступа в handlers
      bot["uow_factory"] = uow_factory
  ```
- Обработка connection pooling и таймаутов
- Graceful shutdown:
  ```python
  async def on_shutdown(bot: Bot):
      uow_factory = bot["uow_factory"]
      # Close all connections
      await uow_factory().engine.dispose()
  ```

### Шаг 3: Реализация Clock адаптера

**Что включить:**
- Использование SystemClock из py_accountant:
  ```python
  from py_accountant.infrastructure.persistence.inmemory.clock import SystemClock
  
  clock = SystemClock()
  bot["clock"] = clock
  ```
- Опциональный wrapper для user timezone:
  ```python
  class UserTimezoneClock(Clock):
      def __init__(self, user_tz: str):
          self.user_tz = ZoneInfo(user_tz)
      
      def now(self) -> datetime:
          return datetime.now(UTC).astimezone(self.user_tz)
  ```

### Шаг 4: Маппинг bot команд → use cases

**Что включить:**
- Полный код handler для `/deposit`:
  ```python
  from aiogram import Router
  from aiogram.filters import Command
  from aiogram.types import Message
  from py_accountant.application.use_cases_async.ledger import AsyncPostTransaction
  from py_accountant.application.dto.models import EntryLineDTO
  
  router = Router()
  
  @router.message(Command("deposit"))
  async def deposit_handler(message: Message, uow_factory, clock):
      # Parse command: /deposit 100 USD from card
      amount, currency = parse_deposit_command(message.text)
      
      # Map to domain concepts
      lines = [
          EntryLineDTO(
              side="DEBIT",
              account_full_name=f"Assets:User:{message.from_user.id}:Cash",
              amount=Decimal(amount),
              currency_code=currency,
              exchange_rate=None
          ),
          EntryLineDTO(
              side="CREDIT",
              account_full_name=f"Income:User:{message.from_user.id}:Deposits",
              amount=Decimal(amount),
              currency_code=currency,
              exchange_rate=None
          ),
      ]
      
      async with uow_factory() as uow:
          use_case = AsyncPostTransaction(uow, clock)
          try:
              tx = await use_case(
                  lines=lines,
                  memo=f"Deposit from Telegram user {message.from_user.username}",
                  meta={"user_id": message.from_user.id, "chat_id": message.chat.id}
              )
              await message.reply(f"✅ Deposit recorded: {tx.id}")
          except Exception as e:
              await message.reply(f"❌ Error: {str(e)}")
  ```

- Аналогично для `/balance`, `/history`, `/rates`
- Пример `/balance`:
  ```python
  from py_accountant.application.use_cases_async.accounts import AsyncGetAccountBalance
  
  @router.message(Command("balance"))
  async def balance_handler(message: Message, uow_factory, clock):
      account_name = f"Assets:User:{message.from_user.id}:Cash"
      
      async with uow_factory() as uow:
          use_case = AsyncGetAccountBalance(uow, clock)
          balance = await use_case(account_full_name=account_name)
          await message.reply(f"💰 Your balance: {balance} USD")
  ```

### Шаг 5: Dependency Injection

**Что включить:**
- Middleware для UoW и Clock:
  ```python
  from aiogram import BaseMiddleware
  from aiogram.types import TelegramObject
  
  class UoWMiddleware(BaseMiddleware):
      def __init__(self, uow_factory):
          self.uow_factory = uow_factory
      
      async def __call__(self, handler, event: TelegramObject, data: dict):
          data["uow_factory"] = self.uow_factory
          return await handler(event, data)
  
  class ClockMiddleware(BaseMiddleware):
      def __init__(self, clock):
          self.clock = clock
      
      async def __call__(self, handler, event: TelegramObject, data: dict):
          data["clock"] = self.clock
          return await handler(event, data)
  ```

- Регистрация middleware:
  ```python
  from aiogram import Dispatcher
  
  dp = Dispatcher()
  
  # Register middlewares
  dp.message.middleware(UoWMiddleware(uow_factory))
  dp.message.middleware(ClockMiddleware(clock))
  
  # Register routers
  dp.include_router(router)
  ```

### Шаг 6: Обработка ошибок

**Что включить:**
- Error handler middleware:
  ```python
  from py_accountant.domain.errors import DomainError, ValidationError
  
  class ErrorHandlerMiddleware(BaseMiddleware):
      async def __call__(self, handler, event, data):
          try:
              return await handler(event, data)
          except ValidationError as e:
              await event.answer(f"❌ Validation error: {e}")
              logger.warning(f"Validation error for user {event.from_user.id}: {e}")
          except DomainError as e:
              await event.answer(f"❌ Business rule violation: {e}")
              logger.error(f"Domain error for user {event.from_user.id}: {e}")
          except Exception as e:
              await event.answer("❌ Internal error. Please try again later.")
              logger.exception(f"Unexpected error for user {event.from_user.id}")
  ```

### Шаг 7: Миграции в production

**Что включить:**
- CI/CD пример (GitHub Actions):
  ```yaml
  name: Deploy Bot
  
  on:
    push:
      branches: [main]
  
  jobs:
    deploy:
      runs-on: ubuntu-latest
      steps:
        - uses: actions/checkout@v3
        
        - name: Run migrations
          env:
            DATABASE_URL: ${{ secrets.DATABASE_URL }}
          run: |
            poetry install
            poetry run alembic upgrade head
        
        - name: Deploy bot
          run: |
            # Deploy to your infrastructure
  ```

- Docker example:
  ```dockerfile
  FROM python:3.13-slim
  
  WORKDIR /app
  
  COPY pyproject.toml poetry.lock ./
  RUN pip install poetry && poetry install --no-dev
  
  COPY . .
  
  # Run migrations on container start
  CMD poetry run alembic upgrade head && poetry run python bot.py
  ```

### Шаг 8: Логирование

**Что включить:**
- Отключение py_accountant logging:
  ```python
  # .env
  PYACC__LOGGING_ENABLED=false
  ```

- Настройка bot logger с structlog:
  ```python
  import structlog
  
  structlog.configure(
      processors=[
          structlog.contextvars.merge_contextvars,
          structlog.processors.add_log_level,
          structlog.processors.TimeStamper(fmt="iso"),
          structlog.processors.JSONRenderer()
      ]
  )
  
  logger = structlog.get_logger()
  ```

- Добавление context vars:
  ```python
  from contextvars import ContextVar
  
  user_id_var: ContextVar[int] = ContextVar("user_id")
  chat_id_var: ContextVar[int] = ContextVar("chat_id")
  
  class LogContextMiddleware(BaseMiddleware):
      async def __call__(self, handler, event, data):
          user_id_var.set(event.from_user.id)
          chat_id_var.set(event.chat.id)
          
          structlog.contextvars.bind_contextvars(
              user_id=event.from_user.id,
              chat_id=event.chat.id
          )
          
          try:
              return await handler(event, data)
          finally:
              structlog.contextvars.clear_contextvars()
  ```

### Шаг 9: Тестирование

**Что включить:**
- Unit-тест handler с mocked UoW:
  ```python
  import pytest
  from unittest.mock import AsyncMock, MagicMock
  
  @pytest.mark.asyncio
  async def test_deposit_handler():
      # Mock message
      message = MagicMock()
      message.text = "/deposit 100 USD"
      message.from_user.id = 123
      message.reply = AsyncMock()
      
      # Mock UoW
      uow_mock = AsyncMock()
      uow_factory = lambda: uow_mock
      
      # Mock clock
      clock = MagicMock()
      clock.now.return_value = datetime.now(UTC)
      
      # Call handler
      await deposit_handler(message, uow_factory, clock)
      
      # Assert
      message.reply.assert_called_once()
      assert "✅" in message.reply.call_args[0][0]
  ```

- Integration тест с InMemoryUnitOfWork:
  ```python
  from py_accountant.infrastructure.persistence.inmemory.uow import InMemoryUnitOfWork
  
  @pytest.mark.asyncio
  async def test_deposit_integration():
      uow = InMemoryUnitOfWork()
      clock = SystemClock()
      
      # Create account first
      async with uow:
          # ... setup accounts
          uow.commit()
      
      # Test deposit
      async with uow:
          use_case = AsyncPostTransaction(uow, clock)
          tx = await use_case(lines=[...])
          assert tx.id is not None
  ```

### Шаг 10: Production checklist

**Что включить:**
- Таблица с чеклистом:
  ```markdown
  | Пункт | Статус | Комментарий |
  |-------|--------|-------------|
  | ✅ DATABASE_URL (sync) настроен | [ ] | Для Alembic миграций |
  | ✅ DATABASE_URL_ASYNC настроен | [ ] | Для runtime |
  | ✅ DB pool settings оптимизированы | [ ] | POOL_SIZE=20, MAX_OVERFLOW=10 |
  | ✅ Миграции применены | [ ] | alembic upgrade head |
  | ✅ Logging настроен | [ ] | LOGGING_ENABLED=false, свой logger |
  | ✅ Error handling middleware | [ ] | Graceful error messages |
  | ✅ Тесты написаны | [ ] | Unit + Integration |
  | ✅ CI/CD pipeline | [ ] | Автоматические миграции |
  | ✅ Monitoring | [ ] | Метрики, alerts |
  | ✅ Backup стратегия | [ ] | pg_dump или managed backup |
  ```

- Database tuning советы:
  ```sql
  -- PostgreSQL tuning for bot workload
  ALTER SYSTEM SET max_connections = 100;
  ALTER SYSTEM SET shared_buffers = '256MB';
  ALTER SYSTEM SET effective_cache_size = '1GB';
  ALTER SYSTEM SET work_mem = '4MB';
  ```

---

## Дополнительные требования

### Код примеров
- Все примеры кода должны быть **полными и работающими**
- Включать import statements
- Включать type hints
- Включать docstrings для сложных функций
- Следовать PEP 8 и ruff правилам

### Стиль изложения
- Дружелюбный, но технически точный
- Объяснять "почему", а не только "как"
- Давать альтернативы (например, InMemory UoW vs SQLAlchemy UoW)
- Указывать потенциальные проблемы (pitfalls) и их решения

### Визуализация
- Добавить ASCII-диаграммы где возможно:
  ```
  ┌─────────────────┐
  │  Telegram Bot   │
  │   (aiogram)     │
  └────────┬────────┘
           │
           ▼
  ┌─────────────────┐
  │   Bot Handlers  │
  │  (commands)     │
  └────────┬────────┘
           │
           ▼
  ┌─────────────────┐
  │  py_accountant  │
  │   Use Cases     │
  └────────┬────────┘
           │
           ▼
  ┌─────────────────┐
  │   PostgreSQL    │
  └─────────────────┘
  ```

### Ссылки
- Ссылки на другие документы проекта (ARCHITECTURE_OVERVIEW.md, RUNNING_MIGRATIONS.md)
- Ссылки на внешние ресурсы (aiogram docs, SQLAlchemy docs)
- Ссылки на примеры в репозитории (если есть)

---

## Ожидаемый результат

После выполнения задачи документ `docs/INTEGRATION_GUIDE.md` должен:
1. Сохранить все существующее содержимое
2. Добавить новый раздел "Детальный пример интеграции: Telegram Bot на aiogram" объёмом **не менее 500 строк**
3. Содержать минимум **10 полных примеров кода**
4. Быть ready-to-use гайдом, по которому разработчик может интегрировать py_accountant в свой проект **без дополнительных вопросов**

---

## Валидация

После написания проверь:
1. ✅ Все примеры кода имеют корректный синтаксис
2. ✅ Все импорты соответствуют актуальной структуре py_accountant
3. ✅ Упомянуты все ключевые use cases (currencies, accounts, ledger, trading, fx_audit)
4. ✅ Покрыты как sync, так и async пути (с акцентом на async)
5. ✅ Есть примеры тестов
6. ✅ Есть production deployment советы

---

## Примечания

- Предполагается, что читатель уже прочитал ARCHITECTURE_OVERVIEW.md и понимает Clean Architecture
- Фокус на практические примеры, а не теоретические объяснения
- Если нужно выбрать между полнотой и краткостью — выбирай полноту
- Лучше повторить важную информацию, чем оставить пробелы

**Начни работу! 🚀**

