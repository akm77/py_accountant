"""Main RPG generator script.

Usage:
    python -m tools.rpg.generate_rpg [OPTIONS]

Options:
    --project-dir PATH      Path to the project directory (default: current directory)
    --output PATH          Path to output YAML file (default: <project_name>_rpg.yaml)
    --src-dir PATH         Source directory to analyze (default: src)
    --exclude PATTERN      Pattern to exclude (can be specified multiple times)
    --version VERSION      Project version (default: read from pyproject.toml)
    --description TEXT     Project description
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    import tomli as tomllib
except ImportError:
    import tomllib  # type: ignore[import-not-found]

from .analyzer import CodeAnalyzer
from .graph_builder import GraphBuilder
from .yaml_writer import YAMLWriter, customize_yaml_dumper


def read_pyproject_toml(project_dir: Path) -> dict[str, str]:
    """Read project metadata from pyproject.toml.

    Args:
        project_dir: Project directory

    Returns:
        Dictionary with 'name', 'version', and 'description' keys
    """
    pyproject_path = project_dir / "pyproject.toml"

    if not pyproject_path.exists():
        return {"name": project_dir.name, "version": "0.1.0", "description": ""}

    try:
        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)

        poetry_data = data.get("tool", {}).get("poetry", {})
        project_data = data.get("project", {})

        # Poetry format
        if poetry_data:
            return {
                "name": poetry_data.get("name", project_dir.name),
                "version": poetry_data.get("version", "0.1.0"),
                "description": poetry_data.get("description", ""),
            }

        # PEP 621 format
        if project_data:
            return {
                "name": project_data.get("name", project_dir.name),
                "version": project_data.get("version", "0.1.0"),
                "description": project_data.get("description", ""),
            }

    except Exception as e:
        print(f"Warning: Could not read pyproject.toml: {e}", file=sys.stderr)

    return {"name": project_dir.name, "version": "0.1.0", "description": ""}


def main() -> None:
    """Main entry point for the RPG generator."""
    parser = argparse.ArgumentParser(
        description="Generate Repository Planning Graph (RPG) for a Python project"
    )

    parser.add_argument(
        "--project-dir",
        type=Path,
        default=Path.cwd(),
        help="Path to the project directory (default: current directory)",
    )

    parser.add_argument(
        "--output",
        type=Path,
        help="Path to output YAML file (default: <project_name>_rpg.yaml)",
    )

    parser.add_argument(
        "--src-dir",
        type=Path,
        default=Path("src"),
        help="Source directory to analyze relative to project-dir (default: src)",
    )

    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="Pattern to exclude (can be specified multiple times)",
    )

    parser.add_argument(
        "--version",
        type=str,
        help="Project version (default: read from pyproject.toml)",
    )

    parser.add_argument(
        "--description",
        type=str,
        help="Project description (default: read from pyproject.toml)",
    )

    parser.add_argument(
        "--docstring",
        action="store_true",
        help="Include docstrings in the output (default: excluded for compact size)",
    )

    parser.add_argument(
        "--nodetail",
        action="store_true",
        help="Create simplified version without method details (default: include methods)",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output",
    )

    args = parser.parse_args()

    # Resolve paths
    project_dir = args.project_dir.resolve()
    if not project_dir.exists():
        print(f"Error: Project directory does not exist: {project_dir}", file=sys.stderr)
        sys.exit(1)

    # Read metadata from pyproject.toml
    metadata = read_pyproject_toml(project_dir)

    project_name = metadata["name"]
    version = args.version or metadata["version"]
    description = args.description or metadata["description"]

    # Determine output path
    if args.output:
        output_path = args.output
    else:
        # Clean project name for filename (replace hyphens with underscores)
        clean_name = project_name.replace("-", "_")
        output_path = project_dir / f"{clean_name}_rpg.yaml"

    # Determine source directory
    src_dir = project_dir / args.src_dir
    if not src_dir.exists():
        # Try root directory if src doesn't exist
        src_dir = project_dir

    if args.verbose:
        print(f"Project directory: {project_dir}")
        print(f"Source directory: {src_dir}")
        print(f"Output file: {output_path}")
        print(f"Project name: {project_name}")
        print(f"Version: {version}")
        print(f"Include docstrings: {args.docstring}")
        print(f"Simplified (no methods): {args.nodetail}")
        print()

    # Default exclusions
    default_exclude = [
        "__pycache__",
        ".pyc",
        ".pyo",
        ".git",
        ".pytest_cache",
        "venv",
        ".venv",
        "env",
        ".env",
        "node_modules",
    ]

    exclude_patterns = default_exclude + args.exclude

    if args.verbose:
        print("Analyzing code...")

    # Step 1: Analyze code
    analyzer = CodeAnalyzer(project_dir)
    modules = analyzer.analyze_directory(src_dir, exclude_patterns)

    if args.verbose:
        print(f"Found {len(modules)} Python modules")
        print()

    if not modules:
        print("Warning: No Python modules found to analyze", file=sys.stderr)
        sys.exit(1)

    # Step 2: Build graph
    if args.verbose:
        print("Building RPG graph...")

    builder = GraphBuilder(project_dir, project_name)
    root = builder.build_graph(
        modules,
        include_docstrings=args.docstring,
        include_methods=not args.nodetail,
    )

    # Calculate metrics
    metrics = builder.calculate_metrics(root)
    dependency_graph = builder.extract_dependency_graph(root)

    if args.verbose:
        print("Metrics:")
        for key, value in metrics.items():
            print(f"  {key}: {value}")
        print()

    # Step 3: Write to YAML
    if args.verbose:
        print(f"Writing RPG to {output_path}...")

    customize_yaml_dumper()

    writer = YAMLWriter(project_name, version)
    writer.write_to_file(
        root,
        output_path,
        description=description,
        metrics=metrics,
        dependency_graph=dependency_graph,
    )

    print(f"✓ RPG generated successfully: {output_path}")
    print(f"  Total files: {metrics['total_files']}")
    print(f"  Total lines: {metrics['total_lines']}")
    print(f"  Total classes: {metrics['total_classes']}")
    print(f"  Total functions: {metrics['total_functions']}")


if __name__ == "__main__":
    main()

