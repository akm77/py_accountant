# Changelog py_accountant

Все значимые изменения в проекте отражены в этом файле.

Формат основан на [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [1.1.0] - 2025-11-25

### Added
- **API_REFERENCE.md** — полный справочник публичного API
  - 17 async use cases с примерами
  - 6 protocols (ports)
  - 14 DTOs
  - Migration guide (sync → async)
  
- **CONFIG_REFERENCE.md** — полный справочник конфигурации
  - 27 переменных окружения
  - Dual-URL architecture
  - Примеры для dev/staging/production
  - Secrets management (AWS, K8s, Vault)
  
- **Examples** — 3 полнофункциональных примера
  - examples/fastapi_basic/ — REST API с FastAPI
  - examples/cli_basic/ — CLI с Typer
  - examples/telegram_bot/ — Telegram бот (документирован)
  
- **Automated Documentation Tests** — 18 тестов
  - Валидация Python синтаксиса в примерах кода
  - Проверка внутренних ссылок
  - Валидация импортов
  - Синхронизация code ↔ docs

### Changed
- Документация обновлена после миграции на core-only архитектуру
- FX_AUDIT.md — CLI заменён на Python API примеры
- RUNNING_MIGRATIONS.md — CLI заменён на Python API
- TRADING_WINDOWS.md — CLI заменён на Python API
- README.md — добавлен async пример + deprecation warning
- ARCHITECTURE_OVERVIEW.md — удалены упоминания presentation layer
- Все примеры используют async-first API

### Fixed
- Исправлены broken links в документации
- Исправлены syntax errors в code examples
- Удалены ссылки на несуществующие компоненты (presentation.cli, sdk)

---

## [1.0.0] - 2025-11-24

### Changed
- Миграция на core-only архитектуру
- Async-first API (AsyncUnitOfWork, use_cases_async)

### Deprecated
- Sync API помечен как deprecated (будет удалён в 2.0.0)

### Removed
- presentation layer (CLI) — удалён из репозитория
- SDK layer — удалён из репозитория

---

**Note**: For detailed documentation update history, see local `docs/audit/` folder (if available).

