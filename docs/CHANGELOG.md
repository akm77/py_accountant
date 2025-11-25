# Changelog документации py_accountant

Все значимые изменения в документации проекта отражены в этом файле.

Формат основан на [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [1.1.0-S8] - 2025-11-25

### Added
- Создан CHANGELOG.md с историей всех изменений документации
- Добавлена секция "Качество документации" в INDEX.md (тесты, покрытие)
- Добавлена секция "История обновлений" в INDEX.md
- Добавлена секция "Новые документы (Sprint S1-S7)" в INDEX.md
- Добавлена секция "Быстрый старт" в INDEX.md
- Создан финальный отчёт DOCUMENTATION_UPDATE_REPORT.md
- Добавлены navigation footers в ключевые документы
- Создан SPRINT_S8_COMPLETED.md — отчёт о финальном спринте

### Changed
- Обновлён INDEX.md с документами Sprint S1-S7
- Обновлён README.md с актуальными quick start примерами
- Улучшена навигация между документами
- Обновлена версия проекта до 1.1.0-S8

---

## [1.1.0-S7] - 2025-11-25

### Fixed
- Исправлен broken link в docs/FINAL_REPORT.md
- Исправлен malformed code block в examples/cli_basic/README.md
- Убраны примеры markdown-ссылок из SPRINT_S7_COMPLETED.md (вызывали false positives в тестах)

### Changed
- Все 18 тестов документации теперь проходят (100%)

### Added
- Создан docs/SPRINT_S7_COMPLETED.md — отчёт о спринте исправлений

---

## [1.1.0-S6] - 2025-11-25

### Added
- tests/docs/test_code_examples.py — валидация 60+ блоков кода (5 тестов)
- tests/docs/test_links.py — проверка 50+ внутренних ссылок (4 теста)
- tests/docs/test_imports.py — валидация 20+ импортов (3 теста)
- tests/docs/test_config_variables.py — проверка 27 переменных (3 теста)
- tests/docs/test_docs_sections_present.py — проверка структуры (3 теста)
- tests/docs/README.md — документация тестов документации
- docs/SPRINT_S6_COMPLETED.md — отчёт о спринте

### Fixed
- Исправлены 2 broken links в docs/AUDIT_PRIORITIES.md
- Обнаружены 12+ syntax errors в API_REFERENCE.md (исправлены в S7)

### Changed
- Добавлена автоматизация проверки качества документации
- Время проверки всей документации < 1 секунда

---

## [1.1.0-S5] - 2025-11-25

### Added
- docs/CONFIG_REFERENCE.md — полный справочник конфигурации (2000+ строк)
- Документация всех 27 переменных окружения
- Секция "Configuration Deep Dive" в INTEGRATION_GUIDE.md
- tools/validate_config.py — валидатор конфигурации
- .env.docker — пример для Docker окружения
- Примеры для dev/staging/production окружений
- Troubleshooting guide для конфигурации
- Документация Dual-URL architecture (sync + async)
- Секция Secrets management (AWS, K8s, Vault)
- docs/SPRINT_S5_COMPLETED.md — отчёт о спринте

### Changed
- Обновлён docker-compose.yml с детальными комментариями
- Обновлён INDEX.md с ссылкой на CONFIG_REFERENCE.md
- Обновлён README.md с секцией API и конфигурация

---

## [1.1.0-S4] - 2025-11-25

### Added
- docs/API_REFERENCE.md — полный справочник публичного API (1500+ строк)
- Документация 17 async use cases с примерами
- Документация 6 protocols (ports)
- Документация 14 основных DTOs
- Секция Migration Guide (sync → async)
- tools/generate_api_docs.py — автогенерация сигнатур
- tools/extract_and_validate_code_examples.py — валидатор примеров
- docs/SPRINT_S4_COMPLETED.md — отчёт о спринте

### Changed
- Обновлён INDEX.md с ссылкой на API_REFERENCE.md
- Обновлён README.md с секцией Documentation

---

## [1.1.0-S3] - 2025-11-25

### Added
- examples/fastapi_basic/ — полнофункциональный REST API пример
  - main.py — FastAPI приложение
  - uow.py — реализация UnitOfWork
  - README.md — документация примера
  - requirements.txt — зависимости
- examples/cli_basic/ — полнофункциональный CLI пример
  - main.py — Typer CLI
  - uow.py — реализация UnitOfWork
  - README.md — документация примера
  - requirements.txt — зависимости
- examples/telegram_bot/CHANGELOG.md — документация состояния
- Секция "Framework Integration Examples" в INTEGRATION_GUIDE.md
- docs/SPRINT_S3_COMPLETED.md — отчёт о спринте

### Changed
- Обновлён examples/__init__.py с документацией всех примеров
- Все примеры используют async-first API
- Улучшена навигация между примерами

---

## [1.1.0-S2] - 2025-11-25

### Fixed
- docs/FX_AUDIT.md — CLI заменён на Python API (3 use cases)
  - Use Case 1: Record exchange rate
  - Use Case 2: Detect stale rates
  - Use Case 3: Archive old events
- docs/RUNNING_MIGRATIONS.md — CLI заменён на Python API
  - Примеры для GitHub Actions и GitLab CI
- docs/TRADING_WINDOWS.md — CLI заменён на Python API
- README.md — добавлен async пример + deprecation warning
- docs/ARCHITECTURE_OVERVIEW.md — удалены упоминания presentation layer

### Removed
- 6 ссылок на presentation.cli.main из документации
- Упоминания несуществующего SDK layer

### Added
- docs/SPRINT_S2_COMPLETED.md — отчёт о спринте

---

## [1.1.0-S1] - 2025-11-25

### Added
- docs/AUDIT_INVENTORY.md — инвентаризация 16 документов
  - Категоризация (User Guides, Technical Guides, Meta, Code)
  - Матрица актуальности документов
- docs/AUDIT_PRIORITIES.md — 42 проблемы (P0-P3)
  - P0=6 (критические)
  - P1=8 (высокий приоритет)
  - P2=15 (средний приоритет)
  - P3=13 (низкий приоритет)
- docs/AUDIT_CODE_MAPPING.md — матрица документация ↔ код
  - 18 use cases (44% документированы)
  - 12 protocols (33% документированы)
  - 14 DTOs (30% документированы)
- docs/AUDIT_REMOVED_COMPONENTS.md — анализ удалённых компонентов
  - Анализ presentation layer (CLI)
  - Анализ SDK layer
  - Рекомендации по обновлению документации
- docs/SPRINT_S1_COMPLETED.md — отчёт о спринте

### Changed
- Проведён полный аудит документации
- Выявлено 42 проблемы требующие исправления

---

## [1.0.1] - 2025-11-24

### Added
- docs/DOCUMENTATION_FIX_PROPOSAL.md — план исправления (10 проблем)
  - 3-фазный план реализации
  - Метрики успеха
  - Управление рисками
- docs/DOCUMENTATION_FIX_SUMMARY.md — краткая сводка
- NEXT_STEPS_DOCUMENTATION.md — инструкции к действию
- prompts/sprint_graph.yaml — граф спринтов S1-S8
- docs/INDEX.md — индекс всей документации

### Changed
- Анализ проблем после интеграции в tgbank
- Время интеграции: 4 часа вместо целевых 30 минут

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

### Known Issues
- Документация содержит ссылки на удалённые компоненты
- Примеры кода используют устаревший API
- Отсутствует полный API Reference
- Отсутствует Config Reference

---

## [0.9.0] - 2025-11-23

### Added
- CORE-01: Core-only интеграция
- Полный async API

### Removed
- Legacy sync UoW удален

---

**Формат записей:**
- **Added** — новые документы, секции, примеры
- **Changed** — обновления существующих документов
- **Fixed** — исправления ошибок, broken links, syntax errors
- **Removed** — удалённые документы или секции
- **Deprecated** — помечено как устаревшее
- **Security** — security-related изменения

**Подробнее**: [DOCUMENTATION_UPDATE_REPORT.md](DOCUMENTATION_UPDATE_REPORT.md)

