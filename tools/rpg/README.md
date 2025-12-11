# RPG Generator

Инструменты для автоматической генерации Repository Planning Graph (RPG) для Python проектов.

## Описание

Этот пакет реализует методологию RPG (Repository Planning Graph) для анализа и визуализации структуры крупных Python проектов. RPG создает граф планирования, где узлы представляют компоненты проекта (модули, классы, функции), а рёбра — их зависимости и порядок реализации.

## Установка

Нет необходимости в установке дополнительных зависимостей — скрипты используют только стандартную библиотеку Python и зависимости, уже установленные в проекте (PyYAML).

Для Python < 3.11 может потребоваться:
```bash
pip install tomli
```

## Использование

### Базовое использование

Генерация RPG для текущего проекта:

```bash
# Из корня проекта
python -m tools.rpg

# С явным указанием директории проекта
python -m tools.rpg --project-dir /path/to/project
```

Это создаст файл `py_accountant_rpg.yaml` (или `<project_name>_rpg.yaml`) в корне проекта.

### Опции командной строки

```bash
python -m tools.rpg [OPTIONS]
```

**Опции:**

- `--project-dir PATH` - Путь к директории проекта (по умолчанию: текущая директория)
- `--output PATH` - Путь к выходному YAML файлу (по умолчанию: `<project_name>_rpg.yaml`)
- `--src-dir PATH` - Директория с исходным кодом относительно project-dir (по умолчанию: `src`)
- `--exclude PATTERN` - Паттерн для исключения (можно указывать несколько раз)
- `--version VERSION` - Версия проекта (по умолчанию: читается из pyproject.toml)
- `--description TEXT` - Описание проекта (по умолчанию: читается из pyproject.toml)
- `--docstring` - Включить docstrings в вывод (по умолчанию: НЕ включать, для экономии ~30% размера)
- `--nodetail` - Упрощённая версия без методов классов (по умолчанию: включать методы, экономит ~40-50% размера)
- `--verbose, -v` - Подробный вывод

### Примеры

**Генерация с пользовательским выходным файлом:**

```bash
python -m tools.rpg --output my_custom_rpg.yaml
```

**Анализ конкретной директории:**

```bash
python -m tools.rpg --src-dir src/py_accountant
```

**Исключение определённых паттернов:**

```bash
python -m tools.rpg --exclude tests --exclude examples --exclude docs
```

**Подробный вывод:**

```bash
python -m tools.rpg --verbose
```

**Компактная версия для LLM с ограниченным контекстом:**

```bash
python -m tools.rpg --nodetail --output rpg_compact.yaml
# Уменьшает размер на ~40-50%, исключая методы
```

**Полная версия с docstrings:**

```bash
python -m tools.rpg --docstring --output rpg_full.yaml
# Включает все docstrings (увеличивает размер на ~40-50%)
```

**Минимальная версия (самая компактная):**

```bash
python -m tools.rpg --nodetail --exclude tests --exclude examples
# Минимальный размер для работы с GPT-4/GPT-3.5
```

**Полный пример с несколькими опциями:**

```bash
python -m tools.rpg \
  --project-dir /Users/admin/PycharmProjects/py_accountant \
  --output output/py_accountant_rpg_detailed.yaml \
  --src-dir src \
  --exclude tests \
  --exclude __pycache__ \
  --version 1.1.0 \
  --description "Async accounting ledger application" \
  --verbose
```

## Структура выходного файла

Генерируемый YAML файл содержит:

```yaml
rpg:
  metadata:
    project_name: "py_accountant"
    version: "1.1.0"
    description: "Project description"
    generated_at: "2025-11-28 12:00:00"
    generator: "rpg_generator.py v0.1.0"
  
  metrics:
    total_directories: 42
    total_files: 150
    total_classes: 75
    total_functions: 200
    total_methods: 350
    total_lines: 15000
    avg_lines_per_file: 100
    files_with_classes: 60
    files_with_functions: 90
  
  structure:
    name: "py_accountant"
    type: "project"
    children:
      - name: "src"
        type: "directory"
        children:
          - name: "py_accountant"
            type: "directory"
            children:
              - name: "domain"
                type: "directory"
                # ...
  
  dependencies:
    "src/py_accountant/domain/accounts.py":
      - "py_accountant.domain.value_objects"
      - "py_accountant.domain.errors"
    # ...
  
  functional_modules:
    - name: "domain"
      type: "directory"
      classes:
        - "Account"
        - "Ledger"
        # ...
      functions:
        - "create_account"
        # ...
```

## Архитектура

Генератор RPG состоит из следующих модулей:

### 1. `analyzer.py` - Анализатор кода

Извлекает информацию из Python файлов:
- Классы и их методы
- Функции
- Импорты и зависимости
- Иерархию модулей

Использует модуль `ast` для парсинга Python кода.

### 2. `graph_builder.py` - Построитель графа

Строит иерархический граф из проанализированных модулей:
- Создаёт узлы для директорий, файлов, классов, функций
- Вычисляет метрики проекта
- Извлекает граф зависимостей

### 3. `yaml_writer.py` - Генератор YAML

Записывает граф в YAML формат:
- Генерирует структурированный YAML
- Добавляет метаданные
- Форматирует для удобочитаемости

### 4. `generate_rpg.py` - Главный скрипт

Координирует процесс генерации:
- Читает параметры из командной строки
- Читает метаданные из pyproject.toml
- Запускает анализ и генерацию

## Методология RPG

Repository Planning Graph (RPG) — это техника для работы с большими проектами, которая использует **структурированный граф планирования** вместо расплывчатых текстовых описаний.

### Основные принципы:

1. **Явная структура**: всегда начинай с построения графа
2. **Топологический порядок**: реализуй зависимости раньше зависящих
3. **Стабильные интерфейсы**: фиксируй входы/выходы до реализации
4. **Модульность**: группируй связанные функции, разделяй несвязанные
5. **Инкрементальная валидация**: тести каждый компонент перед интеграцией

### Узлы графа (двойная семантика):

**Функциональный уровень** (возможности системы):
- Корневые узлы = модули высокого уровня (authentication, data_processing, api)
- Промежуточные узлы = компоненты (user_auth, data_validation)
- Листовые узлы = конкретные функции/классы (validate_email, UserManager)

**Структурный уровень** (организация кода):
- Корневые узлы = директории
- Промежуточные узлы = файлы
- Листовые узлы = функции/классы в файлах

### Рёбра графа:

- **Межмодульные связи**: потоки данных между модулями
- **Внутримодульные связи**: порядок файлов внутри модуля

## Интеграция с проектом

Сгенерированный RPG файл можно использовать для:

1. **Документации структуры проекта** - визуальное представление архитектуры
2. **Анализа зависимостей** - выявление циклических зависимостей
3. **Планирования рефакторинга** - определение порядка изменений
4. **Онбординга новых разработчиков** - быстрое понимание структуры
5. **Отслеживания роста проекта** - метрики и статистика

## Примеры использования в проекте

### Генерация RPG для py_accountant

```bash
cd /Users/admin/PycharmProjects/py_accountant
python -m tools.rpg --verbose
```

Результат: `py_accountant_rpg.yaml` с полным графом проекта.

### Генерация для конкретного модуля

```bash
# Только domain модуль
python -m tools.rpg \
  --src-dir src/py_accountant/domain \
  --output domain_rpg.yaml

# Только infrastructure модуль
python -m tools.rpg \
  --src-dir src/py_accountant/infrastructure \
  --output infrastructure_rpg.yaml
```

### CI/CD интеграция

Добавьте в `.github/workflows/rpg-update.yml`:

```yaml
name: Update RPG

on:
  push:
    branches: [main]
    paths:
      - 'src/**/*.py'

jobs:
  update-rpg:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.13'
      
      - name: Install dependencies
        run: pip install pyyaml
      
      - name: Generate RPG
        run: python -m tools.rpg --verbose
      
      - name: Commit updated RPG
        run: |
          git config --local user.email "action@github.com"
          git config --local user.name "GitHub Action"
          git add *_rpg.yaml
          git commit -m "chore: update RPG graph" || exit 0
          git push
```

## Разработка и расширение

### Добавление новых метрик

Отредактируйте `graph_builder.py`, метод `calculate_metrics()`:

```python
def calculate_metrics(self, root: RPGNode) -> dict[str, Any]:
    metrics = {
        # ... существующие метрики ...
        "custom_metric": 0,  # Ваша новая метрика
    }
    # ... логика расчёта ...
    return metrics
```

### Добавление новых типов узлов

Отредактируйте `analyzer.py` для извлечения новых AST узлов, затем обновите `graph_builder.py` для их обработки.

### Кастомизация формата вывода

Отредактируйте `yaml_writer.py` для изменения структуры выходного YAML.

## Устранение неполадок

**Проблема**: `ImportError: No module named 'tomli'`

**Решение**: Установите tomli для Python < 3.11:
```bash
pip install tomli
```

---

**Проблема**: Не найдены Python модули

**Решение**: Убедитесь, что указана правильная директория с исходным кодом:
```bash
python -m tools.rpg --src-dir src/py_accountant --verbose
```

---

**Проблема**: Ошибки парсинга некоторых файлов

**Решение**: Файлы с синтаксическими ошибками автоматически пропускаются. Проверьте вывод с `--verbose` для деталей.

## Зависимости

- Python >= 3.11 (или Python >= 3.9 с `tomli`)
- PyYAML (уже в зависимостях проекта)

## Лицензия

Часть проекта py-accountant. См. корневой LICENSE файл.

## Автор

Создан в соответствии с методологией RPG для управления крупными Python проектами.

