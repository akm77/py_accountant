# Промпт: Реорганизация документации py_accountant

**Дата**: 2025-11-26  
**Цель**: Разделить документацию на production (docs/) и audit/sprint материалы (docs/audit/)

---

## Контекст

После завершения Sprint S1-S8 по обновлению документации, в папке `docs/` накопилось много файлов аудита и отчётов о спринтах, которые были полезны в процессе работы, но не относятся непосредственно к пакету `py_accountant`.

Необходимо:
- В `docs/` оставить ТОЛЬКО документацию пакета py_accountant
- Файлы аудита/спринтов переместить в `docs/audit/` (локальная папка, в .gitignore)
- Обновить все ссылки и тесты

---

## Цели

### Основная цель
Очистить папку `docs/` от временных/вспомогательных файлов, оставив только документацию продукта.

### Структура после реорганизации

```
docs/
├── API_REFERENCE.md              ✅ Product docs
├── CONFIG_REFERENCE.md           ✅ Product docs
├── INTEGRATION_GUIDE.md          ✅ Product docs
├── INTEGRATION_GUIDE_AIOGRAM.md  ✅ Product docs
├── ARCHITECTURE_OVERVIEW.md      ✅ Product docs
├── ACCOUNTING_CHEATSHEET.md      ✅ Product docs
├── PERFORMANCE.md                ✅ Product docs
├── FX_AUDIT.md                   ✅ Product docs
├── TRADING_WINDOWS.md            ✅ Product docs
├── PARITY_REPORT.md              ✅ Product docs
├── RUNNING_MIGRATIONS.md         ✅ Product docs
├── PROJECT_CRIB_SHEET.md         ✅ Product docs
├── INDEX.md                      ✅ Product docs (updated)
├── CHANGELOG.md                  ✅ Product docs (minimal version)
└── audit/                        📁 New folder (in .gitignore)
    ├── AUDIT_INVENTORY.md
    ├── AUDIT_PRIORITIES.md
    ├── AUDIT_CODE_MAPPING.md
    ├── AUDIT_REMOVED_COMPONENTS.md
    ├── SPRINT_S1_COMPLETED.md
    ├── SPRINT_S2_COMPLETED.md
    ├── SPRINT_S3_COMPLETED.md
    ├── SPRINT_S4_COMPLETED.md
    ├── SPRINT_S5_COMPLETED.md
    ├── SPRINT_S6_COMPLETED.md
    ├── SPRINT_S7_COMPLETED.md
    ├── SPRINT_S8_COMPLETED.md
    ├── DOCUMENTATION_FIX_PROPOSAL.md
    ├── DOCUMENTATION_FIX_SUMMARY.md
    ├── DOCUMENTATION_UPDATE_REPORT.md
    ├── FINAL_REPORT.md
    └── README.md                 (новый, объясняет папку)
```

---

## Задачи

### Задача 1: Создать папку docs/audit и README ✅

**Действие**:
1. Создать `docs/audit/` папку
2. Создать `docs/audit/README.md` с объяснением

**Содержимое docs/audit/README.md**:
```markdown
# Audit & Sprint Materials (Local Only)

**⚠️ This folder is in .gitignore and NOT committed to the repository.**

## Purpose

This folder contains audit materials and sprint reports from the documentation update project (Sprint S1-S8, November 24-25, 2025).

These files were essential during the documentation update process but are not part of the product documentation.

## Contents

### Audit Files (Sprint S1)
- `AUDIT_INVENTORY.md` — Documentation inventory (16 documents)
- `AUDIT_PRIORITIES.md` — 42 issues prioritized (P0-P3)
- `AUDIT_CODE_MAPPING.md` — Code ↔ docs mapping matrix
- `AUDIT_REMOVED_COMPONENTS.md` — Analysis of removed components

### Sprint Reports (S1-S8)
- `SPRINT_S1_COMPLETED.md` — Audit & inventory
- `SPRINT_S2_COMPLETED.md` — Critical fixes (6 P0 issues)
- `SPRINT_S3_COMPLETED.md` — Code examples (FastAPI, CLI, Telegram)
- `SPRINT_S4_COMPLETED.md` — API Reference (1500+ lines)
- `SPRINT_S5_COMPLETED.md` — Config Reference (2000+ lines)
- `SPRINT_S6_COMPLETED.md` — Automated tests (18 tests)
- `SPRINT_S7_COMPLETED.md` — Bug fixes
- `SPRINT_S8_COMPLETED.md` — Final index & changelog

### Documentation Fix Materials
- `DOCUMENTATION_FIX_PROPOSAL.md` — Initial fix proposal (10 issues)
- `DOCUMENTATION_FIX_SUMMARY.md` — Executive summary
- `DOCUMENTATION_UPDATE_REPORT.md` — Final comprehensive report (700+ lines)
- `FINAL_REPORT.md` — Project completion report

## Key Achievements

- ✅ **100% tests passing** (18/18)
- ✅ **100% API coverage** (17 use cases, 6 protocols, 14 DTOs)
- ✅ **100% config coverage** (27 variables)
- ✅ **3 full examples** (FastAPI, CLI, Telegram)
- ✅ **Integration time: 30 minutes** (8x improvement from 4 hours)

## For Developers

If you need to reference these materials:
- They remain in your local `docs/audit/` folder
- They provide historical context for documentation decisions
- Sprint reports contain detailed problem-solving approaches

## See Also

- [../INDEX.md](../INDEX.md) — Current documentation index
- [../CHANGELOG.md](../CHANGELOG.md) — Product changelog
- [../../tests/docs/README.md](../../tests/docs/README.md) — Documentation tests

---

**Created**: 2025-11-26  
**Purpose**: Archive audit & sprint materials locally
```

---

### Задача 2: Обновить .gitignore ✅

**Файл**: `.gitignore`

**Добавить**:
```gitignore
# Documentation audit materials (local only)
docs/audit/
```

**Проверка**:
```bash
# После добавления в .gitignore:
git status
# docs/audit/ не должна появляться в списке
```

---

### Задача 3: Переместить файлы в docs/audit/ ✅

**Список файлов для перемещения**:

```bash
# Audit files
docs/AUDIT_INVENTORY.md
docs/AUDIT_PRIORITIES.md
docs/AUDIT_CODE_MAPPING.md
docs/AUDIT_REMOVED_COMPONENTS.md

# Sprint reports
docs/SPRINT_S1_COMPLETED.md
docs/SPRINT_S2_COMPLETED.md
docs/SPRINT_S3_COMPLETED.md
docs/SPRINT_S4_COMPLETED.md
docs/SPRINT_S5_COMPLETED.md
docs/SPRINT_S6_COMPLETED.md
docs/SPRINT_S7_COMPLETED.md
docs/SPRINT_S8_COMPLETED.md

# Documentation fix materials
docs/DOCUMENTATION_FIX_PROPOSAL.md
docs/DOCUMENTATION_FIX_SUMMARY.md
docs/DOCUMENTATION_UPDATE_REPORT.md
docs/FINAL_REPORT.md
```

**Команда перемещения**:
```bash
# Create audit folder
mkdir -p docs/audit

# Move files
mv docs/AUDIT_*.md docs/audit/
mv docs/SPRINT_S*_COMPLETED.md docs/audit/
mv docs/DOCUMENTATION_FIX_PROPOSAL.md docs/audit/
mv docs/DOCUMENTATION_FIX_SUMMARY.md docs/audit/
mv docs/DOCUMENTATION_UPDATE_REPORT.md docs/audit/
mv docs/FINAL_REPORT.md docs/audit/

# Verify
ls docs/audit/
```

**Проверка после перемещения**:
```bash
# Should show ~17 files
ls -1 docs/audit/ | wc -l

# Should NOT include AUDIT*, SPRINT*, DOCUMENTATION_FIX*, FINAL_REPORT
ls docs/
```

---

### Задача 4: Обновить INDEX.md ✅

**Файл**: `docs/INDEX.md`

**Удалить секции**:
1. "🎉 Статус: Документация полностью обновлена!" — заменить на краткий welcome message
2. "🆕 Новые документы (Sprint S1-S7)" — удалить полностью
3. "📊 Качество документации" — переместить в начало, сократить
4. "📜 История обновлений документации" — удалить или переместить в CHANGELOG.md

**Новая структура INDEX.md**:

```markdown
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
```

**Удалённые секции**:
- "🎉 Статус: Документация полностью обновлена!" (слишком много деталей о спринтах)
- "🆕 Новые документы (Sprint S1-S7)" (audit материалы)
- "📜 История обновлений документации" (перенесено в CHANGELOG.md)
- Все ссылки на AUDIT_*.md, SPRINT_*.md, DOCUMENTATION_*.md

---

### Задача 5: Обновить CHANGELOG.md ✅

**Файл**: `docs/CHANGELOG.md`

**Сократить до минимальной версии** (оставить только product-related changes):

```markdown
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

**Полная история изменений документации**: См. локальную папку `docs/audit/` (если доступна)
```

**Удалено**:
- Детальная история Sprint S1-S8 (перемещена в docs/audit/)
- Внутренние детали процесса документирования

---

### Задача 6: Обновить README.md ✅

**Файл**: `README.md`

**Секция "Documentation Quality"** — упростить:

**Было**:
```markdown
## ✅ Documentation Quality

Our documentation is automatically tested and validated:

```bash
# Run documentation tests
poetry run pytest tests/docs/ -v
# Expected: 18 passed in ~0.3s ✅
```

**Coverage**:
- ✅ 100% of async use cases documented (17/17)
- ✅ 100% of protocols documented (6/6)
- ✅ 100% of DTOs documented (14/14)
- ✅ 100% of config variables documented (27/27)
- ✅ 3 full-featured examples (FastAPI, CLI, Telegram)

**Tests validate**:
- Python syntax in 60+ code examples
- 50+ internal documentation links
- 20+ py_accountant imports
- Configuration sync (code ↔ docs)

See **[tests/docs/README.md](tests/docs/README.md)** for details.
```

**Стало**:
```markdown
## ✅ Documentation Quality

Our documentation is automatically tested:

```bash
poetry run pytest tests/docs/ -v
# 18 tests validate: code syntax, links, imports, config
```

**Coverage**: 100% (17 use cases, 6 protocols, 14 DTOs, 27 config vars)  
See **[tests/docs/README.md](tests/docs/README.md)** for details.
```

**Удалить** из секции "Complete Index":
```markdown
- **[CHANGELOG](docs/CHANGELOG.md)** — Documentation changelog
- **[Final Report](docs/DOCUMENTATION_UPDATE_REPORT.md)** — Complete documentation update report
```

**Новая секция "Complete Index"**:
```markdown
### Complete Index

- **[Documentation Index](docs/INDEX.md)** — Complete documentation catalog
- **[CHANGELOG](docs/CHANGELOG.md)** — Project changelog
```

---

### Задача 7: Обновить тесты документации ✅

**Файл**: `tests/docs/test_links.py`

**Обновить skip_files** для исключения файлов из docs/audit/:

```python
# Skip files that document removed components (historical/audit docs)
skip_files = {
    'README.md',  # Explains historical SDK removal
    'CHANGELOG.md',  # May reference historical changes
}

# Skip entire audit folder (not in repo)
skip_patterns = [
    'audit/',  # All audit materials are local only
]
```

**Обновить метод `test_all_internal_links_valid`**:

```python
def test_all_internal_links_valid(self, all_markdown_files):
    """Все внутренние ссылки во всех документах валидны."""
    total_links = 0
    errors = []
    
    for md_file in all_markdown_files:
        # Skip audit folder files (local only, in .gitignore)
        if 'docs/audit/' in str(md_file):
            continue
            
        links = extract_markdown_links(md_file)
        
        for link in links:
            if is_external_link(link.target):
                continue
                
            # Skip links to audit folder
            if 'audit/' in link.target:
                continue
            
            total_links += 1
            resolved = resolve_link_path(link.source_file, link.target)
            
            if not resolved.exists():
                errors.append(
                    f"Broken link in {md_file.relative_to(Path.cwd())} at line {link.line_number}:\n"
                    f"  Text: {link.text}\n"
                    f"  Target: {link.target}\n"
                    f"  Resolved: {resolved}\n"
                    f"  File does not exist"
                )
    
    assert total_links > 40, f"Ожидается минимум 40 внутренних ссылок, найдено {total_links}"
    
    if errors:
        pytest.fail(f"\n\nFound {len(errors)} broken links:\n\n" + "\n\n".join(errors))
```

**Обновить fixture `all_markdown_files`**:

```python
@pytest.fixture
def all_markdown_files():
    """Все markdown файлы в репозитории (исключая audit/)."""
    root = Path(__file__).parent.parent.parent
    docs_dir = root / 'docs'
    examples_dir = root / 'examples'
    
    md_files = []
    
    # docs/ (excluding audit/)
    for md_file in docs_dir.rglob('*.md'):
        if 'audit' not in str(md_file):
            md_files.append(md_file)
    
    # examples/
    md_files.extend(examples_dir.rglob('*.md'))
    
    # README.md
    md_files.append(root / 'README.md')
    
    return md_files
```

---

### Задача 8: Обновить navigation footers ✅

**Файлы**: `docs/API_REFERENCE.md`, `docs/CONFIG_REFERENCE.md`, `docs/INTEGRATION_GUIDE.md`

**Удалить ссылки на audit файлы** из navigation footers:

**Было**:
```markdown
## Навигация

📚 **[← Назад к INDEX](INDEX.md)** | **[CHANGELOG →](CHANGELOG.md)** | **[Final Report →](DOCUMENTATION_UPDATE_REPORT.md)**

**См. также**:
- [Sprint Graph](../prompts/sprint_graph.yaml) — Граф всех спринтов
- [Tests Documentation](../tests/docs/README.md) — Автоматизированные тесты
```

**Стало**:
```markdown
## Навигация

📚 **[← Назад к INDEX](INDEX.md)** | **[CHANGELOG →](CHANGELOG.md)**

**См. также**:
- [Examples](../examples/) — Готовые примеры кода
- [Tests Documentation](../tests/docs/README.md) — Автоматизированные тесты
```

---

## Порядок выполнения

### Шаг 1: Подготовка (5 минут)

```bash
# 1. Убедитесь, что нет uncommitted changes
git status

# 2. Создайте backup на всякий случай
cp -r docs docs_backup_$(date +%Y%m%d)

# 3. Проверьте, что тесты проходят
poetry run pytest tests/docs/ -v
```

### Шаг 2: Создание структуры (5 минут)

```bash
# 1. Создайте папку docs/audit
mkdir -p docs/audit

# 2. Создайте docs/audit/README.md
# (используйте содержимое из Задачи 1)

# 3. Обновите .gitignore
echo "" >> .gitignore
echo "# Documentation audit materials (local only)" >> .gitignore
echo "docs/audit/" >> .gitignore

# 4. Проверьте .gitignore
git status | grep audit
# Не должно показывать docs/audit/
```

### Шаг 3: Перемещение файлов (10 минут)

```bash
# Переместите файлы
mv docs/AUDIT_*.md docs/audit/
mv docs/SPRINT_S*_COMPLETED.md docs/audit/
mv docs/DOCUMENTATION_FIX_PROPOSAL.md docs/audit/
mv docs/DOCUMENTATION_FIX_SUMMARY.md docs/audit/
mv docs/DOCUMENTATION_UPDATE_REPORT.md docs/audit/
mv docs/FINAL_REPORT.md docs/audit/

# Проверьте
ls -1 docs/audit/ | wc -l
# Должно быть ~17 файлов

ls -1 docs/
# Не должно быть AUDIT*, SPRINT*, DOCUMENTATION_FIX*, FINAL_REPORT
```

### Шаг 4: Обновление документации (20 минут)

```bash
# 1. Обновите INDEX.md (используйте новую версию из Задачи 4)
# 2. Обновите CHANGELOG.md (используйте сокращённую версию из Задачи 5)
# 3. Обновите README.md (упростите Documentation Quality из Задачи 6)
# 4. Обновите navigation footers в:
#    - docs/API_REFERENCE.md
#    - docs/CONFIG_REFERENCE.md
#    - docs/INTEGRATION_GUIDE.md
```

### Шаг 5: Обновление тестов (15 минут)

```bash
# 1. Обновите tests/docs/test_links.py (из Задачи 7)
# 2. Запустите тесты
poetry run pytest tests/docs/ -v

# Ожидается:
# - Меньше проверяемых ссылок (~40-50 вместо 50+)
# - Все тесты должны проходить
# - Нет ошибок про отсутствующие файлы
```

### Шаг 6: Финальная проверка (10 минут)

```bash
# 1. Проверьте структуру docs/
ls -la docs/
# Должно быть ~15 файлов (без audit/)

# 2. Проверьте docs/audit/
ls -la docs/audit/
# Должно быть ~17 файлов + README.md

# 3. Проверьте .gitignore работает
git status
# docs/audit/ не должна появляться

# 4. Запустите все тесты документации
poetry run pytest tests/docs/ -v
# Все должны проходить

# 5. Проверьте INDEX.md
open docs/INDEX.md
# Не должно быть ссылок на audit файлы

# 6. Проверьте README.md
open README.md
# Секция Documentation Quality должна быть сокращена
```

### Шаг 7: Git commit (5 минут)

```bash
# 1. Добавьте изменения
git add .gitignore
git add docs/
git add README.md
git add tests/docs/test_links.py

# 2. Проверьте, что docs/audit/ не в списке
git status
# docs/audit/ не должна быть в списке изменений

# 3. Commit
git commit -m "docs: reorganize documentation structure

- Move audit & sprint materials to docs/audit/ (local only, in .gitignore)
- Update INDEX.md: remove references to audit materials
- Simplify CHANGELOG.md: keep only product-related changes
- Simplify README.md: condense Documentation Quality section
- Update tests: skip docs/audit/ folder
- Update navigation footers: remove audit links

docs/ now contains ONLY product documentation.
Audit materials (AUDIT_*.md, SPRINT_*.md, reports) are in docs/audit/ (gitignored).

Files moved to docs/audit/:
- AUDIT_INVENTORY.md, AUDIT_PRIORITIES.md, AUDIT_CODE_MAPPING.md, AUDIT_REMOVED_COMPONENTS.md
- SPRINT_S1-S8_COMPLETED.md
- DOCUMENTATION_FIX_PROPOSAL.md, DOCUMENTATION_FIX_SUMMARY.md
- DOCUMENTATION_UPDATE_REPORT.md, FINAL_REPORT.md

Tests still passing: 18/18"

# 4. Проверьте коммит
git show --stat
```

---

## Критерии успеха (DoD)

### ✅ Структура

1. **docs/** содержит ТОЛЬКО product документацию:
   - API_REFERENCE.md ✅
   - CONFIG_REFERENCE.md ✅
   - INTEGRATION_GUIDE.md ✅
   - INTEGRATION_GUIDE_AIOGRAM.md ✅
   - ARCHITECTURE_OVERVIEW.md ✅
   - ACCOUNTING_CHEATSHEET.md ✅
   - PERFORMANCE.md ✅
   - FX_AUDIT.md ✅
   - TRADING_WINDOWS.md ✅
   - PARITY_REPORT.md ✅
   - RUNNING_MIGRATIONS.md ✅
   - PROJECT_CRIB_SHEET.md ✅
   - INDEX.md ✅
   - CHANGELOG.md ✅ (сокращён)
   - rpg_intro.txt ✅
   - ~15 файлов total

2. **docs/audit/** содержит audit материалы:
   - AUDIT_*.md (4 файла) ✅
   - SPRINT_S*_COMPLETED.md (8 файлов) ✅
   - DOCUMENTATION_FIX_*.md (2 файла) ✅
   - DOCUMENTATION_UPDATE_REPORT.md ✅
   - FINAL_REPORT.md ✅
   - README.md ✅ (новый)
   - ~18 файлов total

3. **.gitignore** включает `docs/audit/` ✅

### ✅ Документация

4. **INDEX.md** не содержит ссылок на audit файлы ✅
5. **CHANGELOG.md** сокращён до product changes ✅
6. **README.md** упрощён (Documentation Quality) ✅
7. **Navigation footers** не ссылаются на audit файлы ✅

### ✅ Тесты

8. **tests/docs/test_links.py** пропускает docs/audit/ ✅
9. **Все 18 тестов проходят** ✅
10. **Нет ошибок про missing files** ✅

### ✅ Git

11. **docs/audit/** в .gitignore ✅
12. **git status** не показывает docs/audit/ ✅
13. **Коммит сделан** с чистым описанием ✅

---

## Проверка после выполнения

```bash
# 1. Структура docs/
echo "=== docs/ structure ==="
ls -1 docs/ | grep -v audit
# Expected: ~15 files, no AUDIT*, SPRINT*, DOCUMENTATION_FIX*, FINAL_REPORT

# 2. Структура docs/audit/
echo "=== docs/audit/ structure ==="
ls -1 docs/audit/ | wc -l
# Expected: ~18 files

# 3. .gitignore
echo "=== .gitignore check ==="
grep "docs/audit" .gitignore
# Expected: docs/audit/

# 4. Git status
echo "=== git status ==="
git status | grep audit
# Expected: no output (docs/audit/ is ignored)

# 5. Tests
echo "=== tests ==="
poetry run pytest tests/docs/ -v
# Expected: 18 passed

# 6. INDEX.md check
echo "=== INDEX.md check ==="
grep -i "audit\|sprint.*completed\|documentation.*report" docs/INDEX.md
# Expected: no matches (or very minimal)

# 7. Navigation check
echo "=== Navigation footers check ==="
grep -r "DOCUMENTATION_UPDATE_REPORT\|Sprint Graph" docs/*.md
# Expected: no matches in product docs

echo ""
echo "✅ All checks passed!"
```

---

## Rollback (если нужно)

Если что-то пошло не так:

```bash
# 1. Откатите изменения
git reset --hard HEAD

# 2. Восстановите из backup
rm -rf docs
cp -r docs_backup_YYYYMMDD docs

# 3. Удалите .gitignore changes
git checkout .gitignore

# 4. Проверьте
poetry run pytest tests/docs/ -v
```

---

## Примечания

### Почему docs/audit/ в .gitignore?

1. **Audit материалы — временные**: Они были нужны для процесса обновления документации, но не являются частью продукта.

2. **Локальный контекст**: Каждый разработчик может иметь свои audit материалы локально для справки.

3. **Чистота репозитория**: В git должна быть только product документация.

4. **Гибкость**: Можно легко обновлять audit материалы локально без коммитов.

### Что делать с существующими ссылками?

Если в других репозиториях или документах есть ссылки на файлы из docs/audit/:
- Обновите их на новые пути (если нужен доступ)
- Или удалите, если они больше не нужны
- Локально файлы остаются доступны в docs/audit/

### Можно ли восстановить audit материалы?

Да, они остаются в git истории:
```bash
# Найти последний коммит с файлом
git log --all --full-history -- "docs/SPRINT_S8_COMPLETED.md"

# Восстановить файл из коммита
git checkout <commit-hash> -- docs/SPRINT_S8_COMPLETED.md
```

---

**Создано**: 2025-11-26  
**Цель**: Reorganize documentation structure  
**Результат**: Clean docs/ folder with only product documentation

