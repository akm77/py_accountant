"""Тесты для проверки соответствия переменных окружения коду.

Проверяет, что все переменные в CONFIG_REFERENCE.md существуют в settings.py.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest


def extract_documented_variables() -> set[str]:
    """Извлечь все документированные переменные из CONFIG_REFERENCE.md.

    Returns:
        Множество имён переменных
    """
    config_ref = Path(__file__).parent.parent.parent / "docs" / "CONFIG_REFERENCE.md"
    if not config_ref.exists():
        return set()

    content = config_ref.read_text(encoding='utf-8')

    # Ищем заголовки уровня 4: #### VARIABLE_NAME
    variables = set(re.findall(r'^#### ([A-Z_]+)$', content, re.MULTILINE))

    return variables


def extract_code_variables() -> set[str]:
    """Извлечь все переменные из settings.py.

    Returns:
        Множество имён переменных (без PYACC__ префикса)
    """
    settings_file = Path(__file__).parent.parent.parent / "src" / "py_accountant" / "infrastructure" / "config" / "settings.py"
    if not settings_file.exists():
        return set()

    content = settings_file.read_text(encoding='utf-8')

    variables = set()

    # Ищем Field(..., alias="VARIABLE_NAME")
    aliases = re.findall(r'alias=["\']([A-Z_]+)["\']', content)
    variables.update(aliases)

    # Ищем validation_alias=_prefixed("VARIABLE_NAME")
    prefixed = re.findall(r'validation_alias=_prefixed\(["\']([A-Z_]+)["\']\)', content)
    variables.update(prefixed)

    return variables


class TestConfigurationVariables:
    """Тесты для переменных конфигурации."""

    def test_all_code_variables_documented(self):
        """Все переменные из settings.py задокументированы в CONFIG_REFERENCE.md."""
        code_vars = extract_code_variables()
        documented_vars = extract_documented_variables()

        if not documented_vars:
            pytest.skip("CONFIG_REFERENCE.md not found")

        undocumented = code_vars - documented_vars

        if undocumented:
            pytest.fail(
                f"Found {len(undocumented)} undocumented variables in settings.py:\n"
                f"  {', '.join(sorted(undocumented))}\n\n"
                f"Please add documentation for these variables to docs/CONFIG_REFERENCE.md"
            )

    def test_all_documented_variables_exist(self):
        """Все документированные переменные существуют в settings.py."""
        code_vars = extract_code_variables()
        documented_vars = extract_documented_variables()

        if not documented_vars:
            pytest.skip("CONFIG_REFERENCE.md not found")

        nonexistent = documented_vars - code_vars

        if nonexistent:
            pytest.fail(
                f"Found {len(nonexistent)} documented variables that don't exist in settings.py:\n"
                f"  {', '.join(sorted(nonexistent))}\n\n"
                f"Please remove or update these variables in docs/CONFIG_REFERENCE.md"
            )

    def test_variable_count_matches(self):
        """Количество документированных переменных соответствует коду."""
        code_vars = extract_code_variables()
        documented_vars = extract_documented_variables()

        if not documented_vars:
            pytest.skip("CONFIG_REFERENCE.md not found")

        # Должно быть минимум 25 переменных (по данным S5)
        assert len(documented_vars) >= 25, \
            f"Expected at least 25 documented variables, found {len(documented_vars)}"

        # Разница не должна превышать 2 (допустимо небольшое расхождение)
        diff = abs(len(code_vars) - len(documented_vars))
        assert diff <= 2, \
            f"Code has {len(code_vars)} variables, documentation has {len(documented_vars)}, diff={diff}"

