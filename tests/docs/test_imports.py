"""Тесты для проверки импортов в примерах документации.

Проверяет, что все импорты py_accountant в примерах актуальны.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import NamedTuple

import pytest


class Import(NamedTuple):
    """Импорт с метаданными."""
    module: str
    names: list[str]
    source_file: Path
    line_number: int


def extract_imports_from_code(code: str, source_file: Path, code_line_number: int) -> list[Import]:
    """Извлечь импорты из блока кода.

    Args:
        code: Исходный код Python
        source_file: Файл, содержащий код
        code_line_number: Номер строки начала блока кода

    Returns:
        Список Import
    """
    imports = []

    try:
        tree = ast.parse(code)
    except SyntaxError:
        return imports

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(Import(
                    module=alias.name,
                    names=[],
                    source_file=source_file,
                    line_number=code_line_number + (node.lineno if hasattr(node, 'lineno') else 0)
                ))
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names = [alias.name for alias in node.names]
                imports.append(Import(
                    module=node.module,
                    names=names,
                    source_file=source_file,
                    line_number=code_line_number + (node.lineno if hasattr(node, 'lineno') else 0)
                ))

    return imports


def extract_python_blocks(md_file: Path) -> list[tuple[str, int]]:
    """Извлечь блоки кода с номерами строк."""
    content = md_file.read_text(encoding='utf-8')
    blocks = []

    pattern = r'```python\n(.*?)\n```'
    for match in re.finditer(pattern, content, re.DOTALL):
        code = match.group(1)
        line_number = content[:match.start()].count('\n') + 1
        blocks.append((code, line_number))

    return blocks


def is_py_accountant_import(module: str) -> bool:
    """Проверить, является ли импорт из py_accountant."""
    return module.startswith('py_accountant')


def is_external_library(module: str) -> bool:
    """Проверить, является ли импорт внешней библиотекой (игнорировать)."""
    external = ['boto3', 'hvac', 'asyncpg', 'aiosqlite', 'structlog', 'sqlalchemy']
    return any(module.startswith(lib) for lib in external)


@pytest.fixture
def all_markdown_files() -> list[Path]:
    """Список всех markdown файлов в проекте."""
    root = Path(__file__).parent.parent.parent

    # Skip historical/proposal documents with outdated imports
    skip_files = {
        'DOCUMENTATION_FIX_PROPOSAL.md',
        'AUDIT_PRIORITIES.md',
        'AUDIT_REMOVED_COMPONENTS.md',
        'AUDIT_CODE_MAPPING.md',
    }

    files = []
    readme = root / "README.md"
    if readme.exists():
        files.append(readme)

    docs_dir = root / "docs"
    if docs_dir.exists():
        for f in docs_dir.glob("*.md"):
            if f.name not in skip_files:
                files.append(f)

    return files


class TestDocumentationImports:
    """Тесты для импортов в документации."""

    def test_py_accountant_imports_valid(self, all_markdown_files):
        """Все импорты py_accountant в примерах актуальны."""
        errors = []
        total_imports = 0

        for md_file in all_markdown_files:
            blocks = extract_python_blocks(md_file)

            for code, line_number in blocks:
                imports = extract_imports_from_code(code, md_file, line_number)

                for imp in imports:
                    if not is_py_accountant_import(imp.module):
                        continue

                    if is_external_library(imp.module):
                        continue

                    total_imports += 1

                    # Попытаться импортировать
                    try:
                        __import__(imp.module)
                    except ImportError as e:
                        errors.append(
                            f"Invalid import in {md_file.relative_to(Path.cwd())} at line ~{imp.line_number}:\n"
                            f"  Module: {imp.module}\n"
                            f"  Names: {imp.names}\n"
                            f"  Error: {e}"
                        )

        assert total_imports >= 20, f"Ожидается минимум 20 импортов py_accountant, найдено {total_imports}"

        if errors:
            pytest.fail(f"\n\nFound {len(errors)} invalid imports:\n\n" + "\n\n".join(errors))

    def test_no_legacy_imports(self, all_markdown_files):
        """Нет импортов из удалённых модулей (sdk, presentation)."""
        errors = []

        legacy_modules = [
            'py_accountant.sdk',
            'py_accountant.presentation',
        ]

        for md_file in all_markdown_files:
            blocks = extract_python_blocks(md_file)

            for code, line_number in blocks:
                imports = extract_imports_from_code(code, md_file, line_number)

                for imp in imports:
                    for legacy in legacy_modules:
                        if imp.module.startswith(legacy):
                            errors.append(
                                f"Legacy import in {md_file.relative_to(Path.cwd())} at line ~{imp.line_number}:\n"
                                f"  Module: {imp.module}\n"
                                f"  This module was removed in v1.0.0"
                            )

        if errors:
            pytest.fail(f"\n\nFound {len(errors)} legacy imports:\n\n" + "\n\n".join(errors))

    def test_use_cases_async_imports_preferred(self, all_markdown_files):
        """Примеры используют async use cases, а не sync (deprecated)."""
        sync_count = 0
        async_count = 0

        for md_file in all_markdown_files:
            blocks = extract_python_blocks(md_file)

            for code, line_number in blocks:
                imports = extract_imports_from_code(code, md_file, line_number)

                for imp in imports:
                    if imp.module == 'py_accountant.application.use_cases':
                        sync_count += 1
                    elif imp.module == 'py_accountant.application.use_cases_async' or \
                         imp.module.startswith('py_accountant.application.use_cases_async.'):
                        async_count += 1

        # Async должен использоваться чаще, чем sync
        assert async_count >= sync_count * 2, \
            f"Async use cases ({async_count}) должны использоваться чаще, чем sync ({sync_count})"

