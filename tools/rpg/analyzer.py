"""Code analyzer for extracting project structure and dependencies.

Analyzes Python files to extract:
- Classes and their methods
- Functions
- Imports and dependencies
- Module hierarchy
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class FunctionInfo:
    """Information about a function or method."""

    name: str
    line_number: int
    is_async: bool = False
    is_method: bool = False
    docstring: str | None = None
    decorators: list[str] = field(default_factory=list)


@dataclass
class ClassInfo:
    """Information about a class."""

    name: str
    line_number: int
    docstring: str | None = None
    methods: list[FunctionInfo] = field(default_factory=list)
    base_classes: list[str] = field(default_factory=list)
    decorators: list[str] = field(default_factory=list)


@dataclass
class ModuleInfo:
    """Information about a Python module."""

    file_path: Path
    relative_path: Path
    module_name: str
    docstring: str | None = None
    imports: list[str] = field(default_factory=list)
    classes: list[ClassInfo] = field(default_factory=list)
    functions: list[FunctionInfo] = field(default_factory=list)
    line_count: int = 0


class CodeAnalyzer:
    """Analyzes Python code to extract structure and dependencies."""

    def __init__(self, root_path: Path):
        """Initialize the analyzer.

        Args:
            root_path: Root directory of the project
        """
        self.root_path = root_path

    def analyze_file(self, file_path: Path) -> ModuleInfo | None:
        """Analyze a single Python file.

        Args:
            file_path: Path to the Python file

        Returns:
            ModuleInfo object or None if file cannot be parsed
        """
        try:
            content = file_path.read_text(encoding="utf-8")
            tree = ast.parse(content, filename=str(file_path))
        except (SyntaxError, UnicodeDecodeError):
            return None

        relative_path = file_path.relative_to(self.root_path)
        module_name = self._path_to_module_name(relative_path)

        module_info = ModuleInfo(
            file_path=file_path,
            relative_path=relative_path,
            module_name=module_name,
            docstring=ast.get_docstring(tree),
            line_count=len(content.splitlines()),
        )

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module_info.imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    module_info.imports.append(node.module)
            elif isinstance(node, ast.ClassDef):
                class_info = self._extract_class_info(node)
                module_info.classes.append(class_info)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and self._is_top_level_function(tree, node):
                # Only top-level functions
                func_info = self._extract_function_info(node)
                module_info.functions.append(func_info)

        return module_info

    def _extract_class_info(self, node: ast.ClassDef) -> ClassInfo:
        """Extract information from a class definition."""
        base_classes = [self._get_base_name(base) for base in node.bases]

        class_info = ClassInfo(
            name=node.name,
            line_number=node.lineno,
            docstring=ast.get_docstring(node),
            base_classes=base_classes,
            decorators=[self._get_decorator_name(dec) for dec in node.decorator_list],
        )

        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                func_info = self._extract_function_info(item, is_method=True)
                class_info.methods.append(func_info)

        return class_info

    def _extract_function_info(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        is_method: bool = False,
    ) -> FunctionInfo:
        """Extract information from a function definition."""
        return FunctionInfo(
            name=node.name,
            line_number=node.lineno,
            is_async=isinstance(node, ast.AsyncFunctionDef),
            is_method=is_method,
            docstring=ast.get_docstring(node),
            decorators=[self._get_decorator_name(dec) for dec in node.decorator_list],
        )

    def _is_top_level_function(
        self,
        tree: ast.Module,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> bool:
        """Check if a function is defined at module level."""
        return any(item is node for item in tree.body)

    def _get_base_name(self, base: Any) -> str:
        """Get the name of a base class."""
        if isinstance(base, ast.Name):
            return base.id
        elif isinstance(base, ast.Attribute):
            return f"{self._get_attr_chain(base.value)}.{base.attr}"
        return "Unknown"

    def _get_attr_chain(self, node: Any) -> str:
        """Get the full attribute chain (e.g., 'a.b.c')."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{self._get_attr_chain(node.value)}.{node.attr}"
        return ""

    def _get_decorator_name(self, dec: Any) -> str:
        """Get the name of a decorator."""
        if isinstance(dec, ast.Name):
            return dec.id
        elif isinstance(dec, ast.Call):
            if isinstance(dec.func, ast.Name):
                return dec.func.id
            elif isinstance(dec.func, ast.Attribute):
                return f"{self._get_attr_chain(dec.func.value)}.{dec.func.attr}"
        elif isinstance(dec, ast.Attribute):
            return f"{self._get_attr_chain(dec.value)}.{dec.attr}"
        return "unknown"

    def _path_to_module_name(self, path: Path) -> str:
        """Convert a file path to a Python module name."""
        parts = list(path.parts)
        if parts[-1] == "__init__.py":
            parts = parts[:-1]
        else:
            parts[-1] = parts[-1].replace(".py", "")
        return ".".join(parts)

    def analyze_directory(
        self,
        directory: Path,
        exclude_patterns: list[str] | None = None,
    ) -> list[ModuleInfo]:
        """Analyze all Python files in a directory recursively.

        Args:
            directory: Directory to analyze
            exclude_patterns: List of patterns to exclude (e.g., ['__pycache__', '*.pyc'])

        Returns:
            List of ModuleInfo objects
        """
        if exclude_patterns is None:
            exclude_patterns = ["__pycache__", ".pyc", ".pyo", ".git", ".pytest_cache"]

        modules = []
        for file_path in directory.rglob("*.py"):
            # Check if file should be excluded
            if any(pattern in str(file_path) for pattern in exclude_patterns):
                continue

            module_info = self.analyze_file(file_path)
            if module_info:
                modules.append(module_info)

        return modules

