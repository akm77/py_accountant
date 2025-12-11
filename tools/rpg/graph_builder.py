"""Graph builder for creating RPG structure from analyzed code.

Builds a hierarchical graph representation following the RPG methodology:
- Nodes represent modules, files, classes, and functions
- Edges represent dependencies and execution order
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .analyzer import ModuleInfo


@dataclass
class RPGNode:
    """A node in the RPG graph."""

    name: str
    node_type: str  # 'directory', 'file', 'class', 'function'
    path: str | None = None
    children: list[RPGNode] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert node to dictionary representation."""
        result: dict[str, Any] = {
            "name": self.name,
            "type": self.node_type,
        }

        if self.path:
            result["path"] = self.path

        if self.metadata:
            result["metadata"] = self.metadata

        if self.dependencies:
            result["dependencies"] = self.dependencies

        if self.children:
            result["children"] = [child.to_dict() for child in self.children]

        return result


class GraphBuilder:
    """Builds an RPG graph from analyzed modules."""

    def __init__(self, root_path: Path, project_name: str):
        """Initialize the graph builder.

        Args:
            root_path: Root directory of the project
            project_name: Name of the project
        """
        self.root_path = root_path
        self.project_name = project_name
        self.modules_by_path: dict[str, ModuleInfo] = {}
        self.include_docstrings = True
        self.include_methods = True

    def build_graph(
        self,
        modules: list[ModuleInfo],
        include_docstrings: bool = False,
        include_methods: bool = True,
    ) -> RPGNode:
        """Build the complete RPG graph from analyzed modules.

        Args:
            modules: List of analyzed modules
            include_docstrings: Include docstrings in metadata (default: False for compact size)
            include_methods: Include method details in classes (default: True)

        Returns:
            Root node of the RPG graph
        """
        # Store settings
        self.include_docstrings = include_docstrings
        self.include_methods = include_methods

        # Index modules by path
        self.modules_by_path = {str(m.relative_path): m for m in modules}

        # Build directory hierarchy
        root = RPGNode(
            name=self.project_name,
            node_type="project",
            metadata={
                "total_modules": len(modules),
                "total_lines": sum(m.line_count for m in modules),
            },
        )

        # Group modules by directory
        dir_structure = self._build_directory_structure(modules)

        # Build tree recursively
        self._build_tree_recursive(root, dir_structure, "")

        return root

    def _build_directory_structure(
        self,
        modules: list[ModuleInfo],
    ) -> dict[str, Any]:
        """Build a nested dictionary representing the directory structure."""
        structure: dict[str, Any] = {}

        for module in modules:
            parts = list(module.relative_path.parts)
            current = structure

            for part in parts[:-1]:  # All but last (file)
                if part not in current:
                    current[part] = {}
                current = current[part]

            # Add the file
            current[parts[-1]] = module

        return structure

    def _build_tree_recursive(
        self,
        parent_node: RPGNode,
        structure: dict[str, Any],
        current_path: str,
    ) -> None:
        """Recursively build the tree structure."""
        for name, value in sorted(structure.items()):
            path = f"{current_path}/{name}" if current_path else name

            if isinstance(value, ModuleInfo):
                # It's a file
                file_node = self._create_file_node(value)
                parent_node.children.append(file_node)
            else:
                # It's a directory
                dir_node = RPGNode(
                    name=name,
                    node_type="directory",
                    path=path,
                )
                parent_node.children.append(dir_node)
                self._build_tree_recursive(dir_node, value, path)

    def _create_file_node(self, module: ModuleInfo) -> RPGNode:
        """Create a node for a Python file."""
        # Build metadata conditionally
        metadata = {
            "module_name": module.module_name,
            "line_count": module.line_count,
        }

        # Add docstring only if requested
        if self.include_docstrings and module.docstring:
            metadata["docstring"] = module.docstring

        file_node = RPGNode(
            name=module.relative_path.name,
            node_type="file",
            path=str(module.relative_path),
            dependencies=self._extract_internal_dependencies(module),
            metadata=metadata,
        )

        # Add classes
        for class_info in module.classes:
            class_metadata: dict[str, Any] = {
                "line_number": class_info.line_number,
                "base_classes": class_info.base_classes,
                "decorators": class_info.decorators,
                "method_count": len(class_info.methods),
            }

            # Add docstring only if requested
            if self.include_docstrings and class_info.docstring:
                class_metadata["docstring"] = class_info.docstring

            class_node = RPGNode(
                name=class_info.name,
                node_type="class",
                metadata=class_metadata,
            )

            # Add methods only if requested
            if self.include_methods:
                for method in class_info.methods:
                    method_node = RPGNode(
                        name=method.name,
                        node_type="method",
                        metadata={
                            "line_number": method.line_number,
                            "is_async": method.is_async,
                            "decorators": method.decorators,
                        },
                    )
                    class_node.children.append(method_node)

            file_node.children.append(class_node)

        # Add functions
        for func in module.functions:
            func_node = RPGNode(
                name=func.name,
                node_type="function",
                metadata={
                    "line_number": func.line_number,
                    "is_async": func.is_async,
                    "decorators": func.decorators,
                },
            )
            file_node.children.append(func_node)

        return file_node

    def _extract_internal_dependencies(self, module: ModuleInfo) -> list[str]:
        """Extract dependencies that are internal to the project."""
        internal_deps = []

        # Determine the package name from the project structure
        # Typically it's the first directory in src/ or the project itself
        package_prefixes = self._find_package_prefixes()

        for imp in module.imports:
            for prefix in package_prefixes:
                if imp.startswith(prefix):
                    internal_deps.append(imp)
                    break

        return sorted(set(internal_deps))

    def _find_package_prefixes(self) -> list[str]:
        """Find the main package names in the project."""
        prefixes = []

        # Check common patterns
        src_path = self.root_path / "src"
        if src_path.exists():
            for item in src_path.iterdir():
                if item.is_dir() and not item.name.startswith("."):
                    prefixes.append(item.name)

        # Also check root level
        for item in self.root_path.iterdir():
            if (
                item.is_dir()
                and not item.name.startswith(".")
                and (item / "__init__.py").exists()
            ):
                prefixes.append(item.name)

        return prefixes

    def calculate_metrics(self, root: RPGNode) -> dict[str, Any]:
        """Calculate various metrics from the graph.

        Args:
            root: Root node of the graph

        Returns:
            Dictionary of metrics
        """
        metrics = {
            "total_directories": 0,
            "total_files": 0,
            "total_classes": 0,
            "total_functions": 0,
            "total_methods": 0,
            "total_lines": 0,
            "avg_lines_per_file": 0,
            "files_with_classes": 0,
            "files_with_functions": 0,
        }

        self._calculate_metrics_recursive(root, metrics)

        if metrics["total_files"] > 0:
            metrics["avg_lines_per_file"] = int(
                metrics["total_lines"] / metrics["total_files"]
            )

        return metrics

    def _calculate_metrics_recursive(
        self,
        node: RPGNode,
        metrics: dict[str, Any],
    ) -> None:
        """Recursively calculate metrics."""
        if node.node_type == "directory":
            metrics["total_directories"] += 1
        elif node.node_type == "file":
            metrics["total_files"] += 1
            metrics["total_lines"] += node.metadata.get("line_count", 0)

            has_classes = any(c.node_type == "class" for c in node.children)
            has_functions = any(c.node_type == "function" for c in node.children)

            if has_classes:
                metrics["files_with_classes"] += 1
            if has_functions:
                metrics["files_with_functions"] += 1

        elif node.node_type == "class":
            metrics["total_classes"] += 1
        elif node.node_type == "function":
            metrics["total_functions"] += 1
        elif node.node_type == "method":
            metrics["total_methods"] += 1

        for child in node.children:
            self._calculate_metrics_recursive(child, metrics)

    def extract_dependency_graph(self, root: RPGNode) -> dict[str, list[str]]:
        """Extract a flat dependency graph from the tree.

        Args:
            root: Root node of the graph

        Returns:
            Dictionary mapping module paths to their dependencies
        """
        dep_graph: dict[str, list[str]] = defaultdict(list)
        self._extract_dependencies_recursive(root, dep_graph)
        return dict(dep_graph)

    def _extract_dependencies_recursive(
        self,
        node: RPGNode,
        dep_graph: dict[str, list[str]],
    ) -> None:
        """Recursively extract dependencies."""
        if node.node_type == "file" and node.path:
            dep_graph[node.path] = node.dependencies

        for child in node.children:
            self._extract_dependencies_recursive(child, dep_graph)

