"""Тесты для проверки ссылок в документации.

Проверяет, что все внутренние ссылки ведут на существующие файлы и разделы.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import NamedTuple

import pytest


class Link(NamedTuple):
    """Ссылка с метаданными."""
    text: str
    target: str
    source_file: Path
    line_number: int


def extract_markdown_links(md_file: Path) -> list[Link]:
    """Извлечь все markdown ссылки из файла.

    Args:
        md_file: Путь к markdown файлу

    Returns:
        Список Link с информацией о ссылках
    """
    content = md_file.read_text(encoding='utf-8')
    links = []

    # Регулярное выражение для markdown ссылок [text](url)
    pattern = r'\[([^\]]+)\]\(([^\)]+)\)'

    for match in re.finditer(pattern, content):
        text = match.group(1)
        target = match.group(2)
        line_number = content[:match.start()].count('\n') + 1
        links.append(Link(text=text, target=target, source_file=md_file, line_number=line_number))

    return links


def is_external_link(target: str) -> bool:
    """Проверить, является ли ссылка внешней."""
    return target.startswith(('http://', 'https://', 'mailto:', 'ftp://'))


def resolve_link_path(source_file: Path, target: str) -> Path:
    """Разрешить путь ссылки относительно исходного файла.

    Args:
        source_file: Файл, содержащий ссылку
        target: Целевой путь (может содержать #anchor)

    Returns:
        Абсолютный путь к целевому файлу
    """
    # Убрать anchor если есть
    if '#' in target:
        target = target.split('#')[0]

    # Если пусто после удаления anchor, ссылка на текущий файл
    if not target:
        return source_file

    # Разрешить относительный путь
    resolved = (source_file.parent / target).resolve()
    return resolved


@pytest.fixture
def all_markdown_files() -> list[Path]:
    """Список всех markdown файлов в проекте."""
    root = Path(__file__).parent.parent.parent

    files = []
    readme = root / "README.md"
    if readme.exists():
        files.append(readme)

    docs_dir = root / "docs"
    if docs_dir.exists():
        files.extend(docs_dir.glob("*.md"))

    examples_dir = root / "examples"
    if examples_dir.exists():
        files.extend(examples_dir.rglob("*.md"))

    return files


class TestDocumentationLinks:
    """Тесты для ссылок в документации."""

    def test_index_links_valid(self):
        """Все ссылки в INDEX.md ведут на существующие файлы."""
        index = Path(__file__).parent.parent.parent / "docs" / "INDEX.md"
        if not index.exists():
            pytest.skip("INDEX.md not found")

        links = extract_markdown_links(index)

        errors = []
        for link in links:
            if is_external_link(link.target):
                continue

            resolved = resolve_link_path(link.source_file, link.target)
            if not resolved.exists():
                errors.append(
                    f"Broken link in INDEX.md at line {link.line_number}:\n"
                    f"  Text: {link.text}\n"
                    f"  Target: {link.target}\n"
                    f"  Resolved: {resolved}\n"
                    f"  File does not exist"
                )

        if errors:
            pytest.fail("\n\n".join(errors))

    def test_readme_links_valid(self):
        """Все ссылки в README.md ведут на существующие файлы."""
        readme = Path(__file__).parent.parent.parent / "README.md"
        if not readme.exists():
            pytest.skip("README.md not found")

        links = extract_markdown_links(readme)

        errors = []
        for link in links:
            if is_external_link(link.target):
                continue

            resolved = resolve_link_path(link.source_file, link.target)
            if not resolved.exists():
                errors.append(
                    f"Broken link in README.md at line {link.line_number}:\n"
                    f"  Text: {link.text}\n"
                    f"  Target: {link.target}\n"
                    f"  Resolved: {resolved}\n"
                    f"  File does not exist"
                )

        if errors:
            pytest.fail("\n\n".join(errors))

    def test_all_internal_links_valid(self, all_markdown_files):
        """Все внутренние ссылки во всех документах валидны."""
        total_links = 0
        errors = []

        for md_file in all_markdown_files:
            links = extract_markdown_links(md_file)

            for link in links:
                if is_external_link(link.target):
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

        assert total_links > 50, f"Ожидается минимум 50 внутренних ссылок, найдено {total_links}"

        if errors:
            pytest.fail(f"\n\nFound {len(errors)} broken links:\n\n" + "\n\n".join(errors))

    def test_no_legacy_references(self, all_markdown_files):
        """Нет ссылок на удалённые компоненты (sdk, presentation.cli)."""
        errors = []

        legacy_patterns = [
            'py_accountant.sdk',
            'presentation.cli',
            'ApplicationService',
        ]

        # Skip files that document removed components (historical/audit docs)
        skip_files = {
            'README.md',  # Explains historical SDK removal
            'AUDIT_REMOVED_COMPONENTS.md',
            'DOCUMENTATION_FIX_PROPOSAL.md',
            'SPRINT_S1_COMPLETED.md',
            'SPRINT_S2_COMPLETED.md',
            'SPRINT_S2_PROMPT_UPDATED.md',
            'SPRINT_S3_COMPLETED.md',
            'SPRINT_S4_COMPLETED.md',
            'AUDIT_PRIORITIES.md',
            'AUDIT_CODE_MAPPING.md',
            'AUDIT_INVENTORY.md',
            'CHANGELOG.md',  # telegram bot changelog documents migration
            'DOCUMENTATION_UPDATE_REPORT.md',  # Final report documenting what was removed
        }

        for md_file in all_markdown_files:
            # Skip historical/audit documentation
            if md_file.name in skip_files:
                continue

            content = md_file.read_text(encoding='utf-8')

            for pattern in legacy_patterns:
                if pattern in content:
                    # Найти строки с упоминаниями
                    lines = content.split('\n')
                    for i, line in enumerate(lines, 1):
                        if pattern in line:
                            errors.append(
                                f"Legacy reference in {md_file.relative_to(Path.cwd())} at line {i}:\n"
                                f"  Pattern: {pattern}\n"
                                f"  Line: {line.strip()}"
                            )

        if errors:
            pytest.fail(f"\n\nFound {len(errors)} legacy references:\n\n" + "\n\n".join(errors))

