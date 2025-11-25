"""Тесты для примеров кода в документации.

Извлекает все блоки ```python из markdown файлов и проверяет их синтаксис.
Использует подход из tools/extract_and_validate_code_examples.py.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import NamedTuple

import pytest


class CodeBlock(NamedTuple):
    """Блок кода с метаданными."""
    source: str
    line_number: int
    file: Path


def extract_python_blocks(md_file: Path) -> list[CodeBlock]:
    """Извлечь все блоки ```python из markdown файла.

    Args:
        md_file: Путь к markdown файлу

    Returns:
        Список CodeBlock с исходным кодом и метаданными
    """
    content = md_file.read_text(encoding='utf-8')
    blocks = []

    # Регулярное выражение для поиска блоков кода
    pattern = r'```python\n(.*?)\n```'

    for match in re.finditer(pattern, content, re.DOTALL):
        code = match.group(1)
        # Вычислить номер строки
        line_number = content[:match.start()].count('\n') + 1
        blocks.append(CodeBlock(source=code, line_number=line_number, file=md_file))

    return blocks


def is_example_only_code(code: str) -> bool:
    """Проверить, является ли код только примером (не полным кодом).

    Примеры: комментарии типа # ..., placeholder переменные.
    """
    lines = code.strip().split('\n')

    # Если весь код - это комментарии или placeholders
    non_comment_lines = [l for l in lines if l.strip() and not l.strip().startswith('#')]
    if not non_comment_lines:
        return True

    # Если есть только placeholder импорты или присваивания
    if all('...' in line or 'pass' in line for line in non_comment_lines):
        return True

    # Constructor signature examples like: use_case = AsyncCreateAccount(uow: AsyncUnitOfWork)
    if any('use_case =' in line and ('(uow:' in line or 'uow:' in line) for line in lines):
        return True

    # Method signature without body (ends with ) -> ReturnType)
    # This is common in API documentation
    stripped = code.strip()
    if stripped.startswith(('async def', 'def')) and stripped.count('\n') <= 15:
        # Check if it ends with ") -> Something" pattern (no body after)
        if ') ->' in code:
            # Find last line
            last_line = lines[-1].strip()
            # If last line is return type annotation, it's signature-only
            if last_line.startswith(')') or '->' in last_line:
                return True

    # Signature-only blocks (function/method signatures without body)
    if len(lines) <= 10:
        if any(line.strip().startswith(('async def', 'def', 'class')) for line in lines):
            has_body = any(
                line.strip() and
                not line.strip().endswith((':', '...', ')')) and
                not line.strip().startswith(('@', '#', 'async def', 'def', 'class')) and
                line.strip() not in ('...', 'pass') and
                ':' not in line  # not part of signature
                for line in lines
            )
            if not has_body:
                return True

    # Пропускать неполные блоки с явными placeholder комментариями
    if '# ...' in code or '# ... existing code ...' in code:
        return True

    # Пропускать блоки с incomplete code (text like "To change the database")
    if any(line.strip() and not line.strip().startswith('#') and
           ('To change' in line or 'By default' in line or '## ' in line)
           for line in lines):
        return True

    # Пропускать блоки с явными неполными примерами кода (trailing text, not code)
    first_line = lines[0].strip() if lines else ""
    if first_line and not first_line.startswith(('#', 'from', 'import', 'async', 'def', 'class', '@')):
        # If first line doesn't start with typical code patterns, it's probably text
        if not any(c in first_line for c in ['=', '(', '{', '[']):
            return True

    # Skip comparison examples (# ❌ / # ✅)
    if '# ❌' in code or '# ✅' in code:
        return True

    return False


def validate_python_syntax(code: str) -> tuple[bool, str]:
    """Валидировать синтаксис Python кода.

    Args:
        code: Исходный код Python

    Returns:
        Tuple (valid, error_message)
    """
    # Add __future__ import for modern syntax if needed
    prepend = ""
    if '|' in code and 'from __future__' not in code:
        prepend = "from __future__ import annotations\n"

    try:
        ast.parse(prepend + code)
        return True, ""
    except SyntaxError as e:
        return False, f"{e.msg} (line {e.lineno})"


@pytest.fixture
def all_markdown_files() -> list[Path]:
    """Список всех markdown файлов в проекте."""
    root = Path(__file__).parent.parent.parent

    files = []
    # README в корне
    readme = root / "README.md"
    if readme.exists():
        files.append(readme)

    # Все .md в docs/
    docs_dir = root / "docs"
    if docs_dir.exists():
        files.extend(docs_dir.glob("*.md"))

    # Примеры
    examples_dir = root / "examples"
    if examples_dir.exists():
        files.extend(examples_dir.rglob("*.md"))

    return files


class TestCodeExamples:
    """Тесты для примеров кода в документации."""

    def test_readme_examples_valid_syntax(self):
        """Все примеры в README.md синтаксически корректны."""
        readme = Path(__file__).parent.parent.parent / "README.md"
        blocks = extract_python_blocks(readme)

        assert len(blocks) > 0, "README.md должен содержать примеры кода"

        errors = []
        for block in blocks:
            # Пропустить примеры-заглушки
            if is_example_only_code(block.source):
                continue

            valid, error_msg = validate_python_syntax(block.source)
            if not valid:
                errors.append(
                    f"Syntax error in README.md at line {block.line_number}:\n"
                    f"  {error_msg}\n"
                    f"  Code:\n{block.source[:200]}"
                )

        if errors:
            pytest.fail("\n\n".join(errors))

    def test_api_reference_examples_valid_syntax(self):
        """Все примеры в API_REFERENCE.md синтаксически корректны."""
        api_ref = Path(__file__).parent.parent.parent / "docs" / "API_REFERENCE.md"
        if not api_ref.exists():
            pytest.skip("API_REFERENCE.md not found")

        blocks = extract_python_blocks(api_ref)

        assert len(blocks) >= 40, f"API_REFERENCE.md должен содержать 40+ примеров, найдено {len(blocks)}"

        errors = []
        for block in blocks:
            if is_example_only_code(block.source):
                continue

            valid, error_msg = validate_python_syntax(block.source)
            if not valid:
                errors.append(
                    f"Syntax error in API_REFERENCE.md at line {block.line_number}:\n"
                    f"  {error_msg}\n"
                    f"  Code:\n{block.source[:200]}"
                )

        if errors:
            pytest.fail("\n\n".join(errors))

    def test_config_reference_examples_valid_syntax(self):
        """Все примеры в CONFIG_REFERENCE.md синтаксически корректны."""
        config_ref = Path(__file__).parent.parent.parent / "docs" / "CONFIG_REFERENCE.md"
        if not config_ref.exists():
            pytest.skip("CONFIG_REFERENCE.md not found")

        blocks = extract_python_blocks(config_ref)

        assert len(blocks) >= 2, f"CONFIG_REFERENCE.md должен содержать 2+ примеров, найдено {len(blocks)}"

        errors = []
        for block in blocks:
            if is_example_only_code(block.source):
                continue

            valid, error_msg = validate_python_syntax(block.source)
            if not valid:
                errors.append(
                    f"Syntax error in CONFIG_REFERENCE.md at line {block.line_number}:\n"
                    f"  {error_msg}\n"
                    f"  Code:\n{block.source[:200]}"
                )

        if errors:
            pytest.fail("\n\n".join(errors))

    def test_integration_guide_examples_valid_syntax(self):
        """Все примеры в INTEGRATION_GUIDE.md синтаксически корректны."""
        integration = Path(__file__).parent.parent.parent / "docs" / "INTEGRATION_GUIDE.md"
        if not integration.exists():
            pytest.skip("INTEGRATION_GUIDE.md not found")

        blocks = extract_python_blocks(integration)

        assert len(blocks) >= 7, f"INTEGRATION_GUIDE.md должен содержать 7+ примеров, найдено {len(blocks)}"

        errors = []
        for block in blocks:
            if is_example_only_code(block.source):
                continue

            valid, error_msg = validate_python_syntax(block.source)
            if not valid:
                errors.append(
                    f"Syntax error in INTEGRATION_GUIDE.md at line {block.line_number}:\n"
                    f"  {error_msg}\n"
                    f"  Code:\n{block.source[:200]}"
                )

        if errors:
            pytest.fail("\n\n".join(errors))

    def test_all_markdown_files_syntax(self, all_markdown_files):
        """Все примеры во всех markdown файлах синтаксически корректны."""
        total_blocks = 0
        errors = []

        for md_file in all_markdown_files:
            blocks = extract_python_blocks(md_file)
            total_blocks += len(blocks)

            for block in blocks:
                if is_example_only_code(block.source):
                    continue

                valid, error_msg = validate_python_syntax(block.source)
                if not valid:
                    errors.append(
                        f"Syntax error in {md_file.relative_to(Path.cwd())} at line {block.line_number}:\n"
                        f"  {error_msg}\n"
                        f"  Code:\n{block.source[:200]}"
                    )

        assert total_blocks >= 60, f"Ожидается минимум 60 блоков кода, найдено {total_blocks}"

        if errors:
            pytest.fail(f"\n\nFound {len(errors)} syntax errors:\n\n" + "\n\n".join(errors))

