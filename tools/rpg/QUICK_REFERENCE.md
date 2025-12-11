# RPG Generator Quick Reference

## Быстрый старт

### Генерация RPG для текущего проекта

```bash
# Простейший вариант (из корня проекта)
python -m tools.rpg

# С указанием проекта
python -m tools.rpg --project-dir /path/to/project

# С подробным выводом
python -m tools.rpg --verbose
```

## Основные команды

### Базовая генерация

```bash
# Генерация с именем по умолчанию (py_accountant_rpg.yaml)
python -m tools.rpg

# Свой файл вывода
python -m tools.rpg --output my_rpg.yaml

# Анализ конкретной директории
python -m tools.rpg --src-dir src/py_accountant
```

### Режимы детализации

```bash
# Базовый режим (по умолчанию) - без docstrings, с методами
python -m tools.rpg

# Компактный режим - без docstrings, без методов (~40-50% меньше)
python -m tools.rpg --nodetail

# Полный режим - с docstrings, с методами
python -m tools.rpg --docstring

# Минимальный режим - самый компактный
python -m tools.rpg --nodetail --exclude tests --exclude examples
```

### Фильтрация

```bash
# Исключить тесты и примеры
python -m tools.rpg --exclude tests --exclude examples

# Исключить несколько паттернов
python -m tools.rpg \
  --exclude tests \
  --exclude examples \
  --exclude __pycache__
```

### Метаданные

```bash
# Установить версию и описание
python -m tools.rpg \
  --version 1.1.0 \
  --description "My awesome project"
```

## Программное использование

### Базовый пример

```python
from pathlib import Path
from tools.rpg.analyzer import CodeAnalyzer
from tools.rpg.graph_builder import GraphBuilder
from tools.rpg.yaml_writer import YAMLWriter

# Анализ
analyzer = CodeAnalyzer(Path("/path/to/project"))
modules = analyzer.analyze_directory(Path("/path/to/src"))

# Построение графа
builder = GraphBuilder(Path("/path/to/project"), "my_project")
root = builder.build_graph(modules)

# Запись в YAML
writer = YAMLWriter("my_project", "1.0.0")
writer.write_to_file(root, Path("output.yaml"))
```

### С метриками и зависимостями

```python
# Метрики
metrics = builder.calculate_metrics(root)
print(f"Total files: {metrics['total_files']}")
print(f"Total lines: {metrics['total_lines']}")

# Граф зависимостей
deps = builder.extract_dependency_graph(root)
for module, deps_list in deps.items():
    print(f"{module} depends on: {deps_list}")
```

## Структура выходного файла

```yaml
rpg:
  metadata:
    project_name: "project-name"
    version: "1.0.0"
    description: "..."
    generated_at: "2025-11-28 12:00:00"
  
  metrics:
    total_files: 52
    total_classes: 112
    total_functions: 46
    # ...
  
  structure:
    name: "project-name"
    type: "project"
    children:
      - name: "src"
        children: [...]
  
  dependencies:
    "path/to/module.py": ["dep1", "dep2"]
  
  functional_modules:
    - name: "domain"
      classes: ["Class1", "Class2"]
```

## Примеры использования

### 1. Генерация для py_accountant

```bash
cd /Users/admin/PycharmProjects/py_accountant
python -m tools.rpg --verbose
```

### 2. Генерация для конкретного модуля

```bash
# Только domain
python -m tools.rpg \
  --src-dir src/py_accountant/domain \
  --output domain_rpg.yaml

# Только infrastructure  
python -m tools.rpg \
  --src-dir src/py_accountant/infrastructure \
  --output infrastructure_rpg.yaml
```

### 3. Анализ изменений

```bash
# До изменений
python -m tools.rpg --output before.yaml

# После изменений
python -m tools.rpg --output after.yaml

# Сравнение
diff before.yaml after.yaml
```

### 4. CI/CD интеграция

```bash
# В GitHub Actions
- name: Generate RPG
  run: python -m tools.rpg --output rpg_$(date +%Y%m%d).yaml
```

## Полезные флаги

| Флаг | Описание | Пример |
|------|----------|--------|
| `--project-dir` | Корневая директория проекта | `--project-dir .` |
| `--output` | Файл вывода | `--output output.yaml` |
| `--src-dir` | Директория с исходным кодом | `--src-dir src` |
| `--exclude` | Паттерн исключения | `--exclude tests` |
| `--version` | Версия проекта | `--version 1.0.0` |
| `--description` | Описание проекта | `--description "..."` |
| `--docstring` | Включить docstrings (+40% размера) | `--docstring` |
| `--nodetail` | Без методов (-40-50% размера) | `--nodetail` |
| `--verbose` | Подробный вывод | `--verbose` |

## Типичные сценарии

### Анализ структуры проекта

```bash
python -m tools.rpg --verbose > analysis.log
```

### Мониторинг роста проекта

```bash
# Еженедельно
python -m tools.rpg --output rpg_week$(date +%U).yaml
```

### Документация для команды

```bash
# Полный граф
python -m tools.rpg --output docs/project_structure.yaml

# Только ядро
python -m tools.rpg \
  --src-dir src/core \
  --output docs/core_structure.yaml
```

## Поиск и устранение проблем

### Нет модулей

**Проблема**: "No Python modules found"

**Решение**:
```bash
# Проверьте src-dir
python -m tools.rpg --src-dir src --verbose

# Или используйте корень
python -m tools.rpg --src-dir . --verbose
```

### Ошибки парсинга

**Проблема**: Некоторые файлы не парсятся

**Решение**: Файлы с синтаксическими ошибками автоматически пропускаются. Используйте `--verbose` для деталей.

### Слишком много файлов

**Проблема**: RPG файл слишком большой

**Решение**:
```bash
# Исключите ненужное
python -m tools.rpg \
  --exclude tests \
  --exclude examples \
  --exclude migrations
```

## Интеграция с инструментами

### Pre-commit hook

```yaml
# .pre-commit-config.yaml
- repo: local
  hooks:
    - id: rpg-update
      name: Update RPG
      entry: python -m tools.rpg
      language: system
      pass_filenames: false
```

### Makefile

```makefile
.PHONY: rpg
rpg:
	python -m tools.rpg --verbose

.PHONY: rpg-modules
rpg-modules:
	python -m tools.rpg --src-dir src/py_accountant/domain --output domain_rpg.yaml
	python -m tools.rpg --src-dir src/py_accountant/infrastructure --output infra_rpg.yaml
	python -m tools.rpg --src-dir src/py_accountant/application --output app_rpg.yaml
```

### VS Code Task

```json
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "Generate RPG",
      "type": "shell",
      "command": "python -m tools.rpg --verbose",
      "group": "build"
    }
  ]
}
```

## API Reference

### CodeAnalyzer

```python
analyzer = CodeAnalyzer(root_path: Path)
modules = analyzer.analyze_directory(
    directory: Path,
    exclude_patterns: list[str] | None = None
)
```

### GraphBuilder

```python
builder = GraphBuilder(root_path: Path, project_name: str)
root = builder.build_graph(modules: list[ModuleInfo])
metrics = builder.calculate_metrics(root: RPGNode)
deps = builder.extract_dependency_graph(root: RPGNode)
```

### YAMLWriter

```python
writer = YAMLWriter(project_name: str, version: str)
writer.write_to_file(
    root: RPGNode,
    output_path: Path,
    description: str | None = None,
    metrics: dict[str, Any] | None = None,
    dependency_graph: dict[str, list[str]] | None = None
)
```

## Подробная документация

См. [README.md](README.md) для полной документации.

