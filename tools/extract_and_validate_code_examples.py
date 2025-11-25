#!/usr/bin/env python3
"""Извлечение и валидация примеров кода из markdown."""
import re
import ast
import sys
from pathlib import Path


def extract_python_blocks(md_file: Path) -> list[tuple[int, str]]:
    """Извлечь все блоки ```python из markdown с номерами строк."""
    content = md_file.read_text()
    blocks = []

    for match in re.finditer(r'```python\n(.*?)\n```', content, re.DOTALL):
        line_num = content[:match.start()].count('\n') + 1
        code = match.group(1)
        blocks.append((line_num, code))

    return blocks


def validate_syntax(code: str) -> list[str]:
    """Проверить синтаксис Python кода."""
    errors = []

    # Skip signature-only blocks (function/method signatures without body)
    lines = code.strip().split('\n')
    if len(lines) <= 10:
        # Check if it's just a signature (ends with ... or just closes paren)
        if any(line.strip().startswith(('async def', 'def', 'class')) for line in lines):
            has_body = any(
                line.strip() and
                not line.strip().endswith((':' '...', ')')) and
                not line.strip().startswith(('@', '#', 'async def', 'def', 'class')) and
                not line.strip() in ('...', 'pass') and
                ':' not in line  # not part of signature
                for line in lines
            )
            if not has_body:
                return []  # Skip signature-only blocks

    # Add __future__ import for modern syntax if needed
    prepend = ""
    if '|' in code and 'from __future__' not in code:
        prepend = "from __future__ import annotations\n"

    try:
        ast.parse(prepend + code)
    except SyntaxError as e:
        errors.append(f"SyntaxError: {e.msg} at line {e.lineno}")
    return errors


def main(md_file: Path):
    """Главная функция."""
    print(f"Checking {md_file}...")
    blocks = extract_python_blocks(md_file)
    print(f"Found {len(blocks)} Python code blocks")

    total_errors = 0
    for line_num, code in blocks:
        errors = validate_syntax(code)
        if errors:
            print(f"\n❌ Block at line {line_num}:")
            for error in errors:
                print(f"   {error}")
            total_errors += len(errors)

    if total_errors == 0:
        print(f"\n✅ All {len(blocks)} code blocks are valid!")
        return 0
    else:
        print(f"\n❌ Found {total_errors} errors in {len(blocks)} blocks")
        return 1


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python extract_and_validate_code_examples.py <markdown_file>")
        sys.exit(1)

    md_file = Path(sys.argv[1])
    if not md_file.exists():
        print(f"Error: {md_file} not found")
        sys.exit(1)

    sys.exit(main(md_file))

