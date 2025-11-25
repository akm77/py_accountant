# 📚 Индекс документации py_accountant

**Последнее обновление:** 26 ноября 2025  
**Версия проекта:** 1.1.0

---

## 🚀 Быстрый старт

### Новому пользователю (5-10 минут)

1. **[README.md](../README.md)** — Обзор проекта и quick start
2. **[INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md)** — Пошаговая интеграция
3. **[examples/](../examples/)** — Готовые примеры кода
   - [fastapi_basic/](../examples/fastapi_basic/) — REST API с FastAPI
   - [cli_basic/](../examples/cli_basic/) — CLI с Typer
   - [telegram_bot/](../examples/telegram_bot/) — Telegram бот

### Разработчику (30 минут)

1. **[API_REFERENCE.md](API_REFERENCE.md)** — Полный справочник API
2. **[CONFIG_REFERENCE.md](CONFIG_REFERENCE.md)** — Конфигурация окружения
3. **[ARCHITECTURE_OVERVIEW.md](ARCHITECTURE_OVERVIEW.md)** — Архитектура
4. **[tests/docs/README.md](../tests/docs/README.md)** — Тесты документации

---

## ✅ Качество документации

```bash
# Run documentation tests
poetry run pytest tests/docs/ -v
# Expected: 18 passed in ~0.4s ✅
```

**Coverage**: 100% (API, protocols, DTOs, config)  
**Tests**: 18 automated tests validating docs

---

## 📖 Документация для пользователей

### API Reference

- **[API_REFERENCE.md](API_REFERENCE.md)** — 📘 Полный справочник по публичному API
  - 17 async use cases с примерами
  - 6 protocols (ports) для реализации
  - 14 DTOs (Data Transfer Objects)
  - Миграция с sync на async API

- **[CONFIG_REFERENCE.md](CONFIG_REFERENCE.md)** — 📘 Полный справочник по конфигурации окружения
  - 27 переменных окружения с детальным описанием
  - Dual-URL architecture (DATABASE_URL + DATABASE_URL_ASYNC)
  - Примеры для dev/staging/production
  - Connection pooling и retry настройки
  - FX TTL конфигурация
  - Secrets management (AWS, K8s, Vault)
  - Troubleshooting guide

### Руководства по интеграции

- **[INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md)** — Как использовать py_accountant в вашем проекте
  - Dual-URL setup (sync для миграций, async для runtime)
  - Configuration Deep Dive
  - Примеры реализации UoW
  - Вызов use cases
  - Secrets management patterns

- **[INTEGRATION_GUIDE_AIOGRAM.md](INTEGRATION_GUIDE_AIOGRAM.md)** — Интеграция с Telegram ботом (aiogram 3.x)

- **[ACCOUNTING_CHEATSHEET.md](ACCOUNTING_CHEATSHEET.md)** — Шпаргалка по бухгалтерии
  - Основы двойной записи
  - Дебет/кредит
  - Типы счетов
  - Примеры проводок

### Технические руководства

- **[ARCHITECTURE_OVERVIEW.md](ARCHITECTURE_OVERVIEW.md)** — Архитектура проекта
  - Clean Architecture (Domain/Application/Infrastructure)
  - Диаграммы слоев
  - Потоки данных
  - Порты и адаптеры

- **[PERFORMANCE.md](PERFORMANCE.md)** — Производительность
  - Индексы базы данных
  - Оптимизации запросов
  - Агрегаты (account_balances, account_daily_turnovers)
  - Benchmarks

- **[RUNNING_MIGRATIONS.md](RUNNING_MIGRATIONS.md)** — Запуск миграций
  - Alembic setup
  - CI/CD integration (GitHub Actions, GitLab CI)
  - Checklist для production

### Специализированные темы

- **[FX_AUDIT.md](FX_AUDIT.md)** — Audit trail курсов валют
  - Exchange rate events
  - TTL и архивация
  - Compliance tracking

- **[TRADING_WINDOWS.md](TRADING_WINDOWS.md)** — Торговые окна
  - Концепция торговых окон
  - Snapshot баланса
  - Reporting

- **[PARITY_REPORT.md](PARITY_REPORT.md)** — Отчет о паритете
  - Проверка консистентности
  - Multi-currency balances
  - Reconciliation

---

## 🛠️ Документация для разработчиков

### Руководства по вкладу

- **[PROJECT_CRIB_SHEET.md](PROJECT_CRIB_SHEET.md)** — Шпаргалка разработчика
  - Структура проекта
  - Соглашения о коде
  - Как добавить новый use case
  - Тестирование

### Архитектурные решения

- **[rpg_intro.txt](rpg_intro.txt)** — Введение в RPG (Repository Planning Graph)
  - Методология разработки
  - Структура RPG-графа
  - Как обновлять граф

---

## 🎯 Навигация по темам

### Я хочу...

#### ...интегрировать py_accountant в свой проект
1. Начните с [INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md)
2. Изучите [ACCOUNTING_CHEATSHEET.md](ACCOUNTING_CHEATSHEET.md) для понимания концепций
3. Изучите [examples/](../examples/) для готовых примеров

#### ...понять архитектуру проекта
1. [ARCHITECTURE_OVERVIEW.md](ARCHITECTURE_OVERVIEW.md) — общий обзор
2. [rpg_intro.txt](rpg_intro.txt) — методология RPG
3. [PROJECT_CRIB_SHEET.md](PROJECT_CRIB_SHEET.md) — детали реализации

#### ...оптимизировать производительность
1. [PERFORMANCE.md](PERFORMANCE.md) — индексы и оптимизации
2. [ARCHITECTURE_OVERVIEW.md](ARCHITECTURE_OVERVIEW.md) — паттерны CQRS

#### ...работать с курсами валют
1. [FX_AUDIT.md](FX_AUDIT.md) — audit trail
2. [INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md) — примеры использования

#### ...запустить в production
1. [RUNNING_MIGRATIONS.md](RUNNING_MIGRATIONS.md) — миграции
2. [INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md) — dual-URL setup
3. [PERFORMANCE.md](PERFORMANCE.md) — индексы

#### ...внести вклад в проект
1. [PROJECT_CRIB_SHEET.md](PROJECT_CRIB_SHEET.md) — getting started
2. [ARCHITECTURE_OVERVIEW.md](ARCHITECTURE_OVERVIEW.md) — понимание слоев
3. [rpg_intro.txt](rpg_intro.txt) — методология

---

## 🔄 История версий документации

### v1.1.0 (2025-11-25) — CURRENT
- ✅ Полная документация API (17 use cases)
- ✅ Полная документация конфигурации (27 переменных)
- ✅ 3 полнофункциональных примера
- ✅ 18 автоматизированных тестов документации
- ✅ Integration time: 30 minutes

См. [CHANGELOG.md](CHANGELOG.md) для деталей.

---

## 📞 Контакты и поддержка

### Нашли ошибку в документации?
1. Создайте issue в репозитории
2. Или создайте PR с исправлением
3. Все документы автоматически тестируются

### Вопросы по использованию?
1. Проверьте существующие issues в репозитории
2. Создайте новый issue с тегом `question`
3. Изучите [examples/](../examples/) — готовые примеры

### Хотите внести вклад?
1. Прочитайте [PROJECT_CRIB_SHEET.md](PROJECT_CRIB_SHEET.md)
2. Изучите открытые issues
3. Создайте PR

---

## 🎓 Методология

Проект следует принципам:
- **RPG (Repository Planning Graph)** — структурированное планирование
- **Clean Architecture** — разделение на слои Domain/Application/Infrastructure
- **Test-Driven Documentation** — тесты определяют качество
- **KISS** — Keep It Simple, Stupid
- **DRY** — Don't Repeat Yourself
- **Async-first** — асинхронный API по умолчанию

См. [rpg_intro.txt](rpg_intro.txt) и [ARCHITECTURE_OVERVIEW.md](ARCHITECTURE_OVERVIEW.md) для деталей.

