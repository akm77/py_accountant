"""YAML writer for RPG graphs.

Generates YAML output in the format compatible with rpg_py_accountant.yaml.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from .graph_builder import RPGNode


class YAMLWriter:
    """Writes RPG graphs to YAML format."""

    def __init__(self, project_name: str, version: str = "1.0.0"):
        """Initialize the YAML writer.

        Args:
            project_name: Name of the project
            version: Version of the project
        """
        self.project_name = project_name
        self.version = version

    def write_to_file(
        self,
        root: RPGNode,
        output_path: Path,
        description: str | None = None,
        metrics: dict[str, Any] | None = None,
        dependency_graph: dict[str, list[str]] | None = None,
    ) -> None:
        """Write the RPG graph to a YAML file.

        Args:
            root: Root node of the RPG graph
            output_path: Path to write the YAML file
            description: Optional project description
            metrics: Optional project metrics
            dependency_graph: Optional dependency graph
        """
        rpg_data = self._build_rpg_structure(
            root,
            description,
            metrics,
            dependency_graph,
        )

        with open(output_path, "w", encoding="utf-8") as f:
            yaml.dump(
                rpg_data,
                f,
                allow_unicode=True,
                default_flow_style=False,
                sort_keys=False,
                width=120,
            )

    def _build_rpg_structure(
        self,
        root: RPGNode,
        description: str | None,
        metrics: dict[str, Any] | None,
        dependency_graph: dict[str, list[str]] | None,
    ) -> dict[str, Any]:
        """Build the complete RPG YAML structure."""
        now = datetime.now()

        rpg_data: dict[str, Any] = {
            "rpg": {
                "metadata": {
                    "project_name": self.project_name,
                    "version": self.version,
                    "description": description
                    or f"Auto-generated RPG for {self.project_name}",
                    "generated_at": now.strftime("%Y-%m-%d %H:%M:%S"),
                    "generator": "rpg_generator.py v0.1.0",
                }
            }
        }

        # Add metrics if available
        if metrics:
            rpg_data["rpg"]["metrics"] = metrics

        # Add structure
        rpg_data["rpg"]["structure"] = self._node_to_structure_dict(root)

        # Add dependency graph if available
        if dependency_graph:
            rpg_data["rpg"]["dependencies"] = dependency_graph

        # Add functional modules (high-level view)
        rpg_data["rpg"]["functional_modules"] = self._extract_functional_modules(root)

        return rpg_data

    def _node_to_structure_dict(self, node: RPGNode) -> dict[str, Any]:
        """Convert an RPG node to a structure dictionary."""
        result: dict[str, Any] = {
            "name": node.name,
            "type": node.node_type,
        }

        if node.path:
            result["path"] = node.path

        if node.metadata:
            # Filter out None values and empty strings
            metadata = {
                k: v
                for k, v in node.metadata.items()
                if v is not None and v != "" and v != []
            }
            if metadata:
                result["metadata"] = metadata

        if node.dependencies:
            result["dependencies"] = node.dependencies

        if node.children:
            result["children"] = [
                self._node_to_structure_dict(child) for child in node.children
            ]

        return result

    def _extract_functional_modules(self, root: RPGNode) -> list[dict[str, Any]]:
        """Extract high-level functional modules from the structure.

        This creates a simplified view focusing on the main architectural components.
        """
        modules = []

        for child in root.children:
            if child.node_type == "directory" and child.name not in [
                "__pycache__",
                ".git",
                ".pytest_cache",
                "tests",
            ]:
                module_info = self._describe_module(child)
                if module_info:
                    modules.append(module_info)

        return modules

    def _describe_module(self, node: RPGNode) -> dict[str, Any] | None:
        """Create a high-level description of a module."""
        if node.node_type not in ["directory", "file"]:
            return None

        # Count components
        classes = []
        functions = []
        submodules = []

        self._collect_components(node, classes, functions, submodules)

        if not classes and not functions and not submodules:
            return None

        description: dict[str, Any] = {
            "name": node.name,
            "type": node.node_type,
        }

        if node.path:
            description["path"] = node.path

        if classes:
            class_names: list[str] = [c["name"] for c in classes[:10]]  # Limit to 10
            if len(classes) > 10:
                class_names.append(f"... and {len(classes) - 10} more")
            description["classes"] = class_names

        if functions:
            func_names: list[str] = [f["name"] for f in functions[:10]]
            if len(functions) > 10:
                func_names.append(f"... and {len(functions) - 10} more")
            description["functions"] = func_names

        if submodules:
            description["submodules"] = [s["name"] for s in submodules]

        return description

    def _collect_components(
        self,
        node: RPGNode,
        classes: list[dict[str, Any]],
        functions: list[dict[str, Any]],
        submodules: list[dict[str, Any]],
    ) -> None:
        """Recursively collect components from a node."""
        for child in node.children:
            if child.node_type == "class":
                classes.append({"name": child.name})
            elif child.node_type == "function":
                functions.append({"name": child.name})
            elif child.node_type == "directory":
                submodules.append({"name": child.name})
                # Don't recurse into subdirectories for functional view
            elif child.node_type == "file":
                # Recurse into files to get their classes and functions
                self._collect_components(child, classes, functions, submodules)


def customize_yaml_dumper() -> None:
    """Customize YAML dumper for better formatting."""

    # Represent None as empty string instead of null
    def represent_none(self: Any, _: Any) -> Any:
        return self.represent_scalar("tag:yaml.org,2002:null", "")

    yaml.add_representer(type(None), represent_none)

    # Better multi-line string representation
    def represent_str(self: Any, data: str) -> Any:
        if "\n" in data:
            return self.represent_scalar("tag:yaml.org,2002:str", data, style="|")
        return self.represent_scalar("tag:yaml.org,2002:str", data)

    yaml.add_representer(str, represent_str)

