#!/usr/bin/env python3
"""Quick example: Generate RPG for the py_accountant project.

This script demonstrates basic usage of the RPG generator.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from tools.rpg.analyzer import CodeAnalyzer  # noqa: E402
from tools.rpg.graph_builder import GraphBuilder  # noqa: E402
from tools.rpg.yaml_writer import YAMLWriter, customize_yaml_dumper  # noqa: E402


def main():
    """Generate RPG for py_accountant project."""
    # Configuration
    project_dir = Path(__file__).parent.parent.parent
    src_dir = project_dir / "src"
    output_file = project_dir / "py_accountant_rpg_example.yaml"

    print(f"Analyzing project at: {project_dir}")
    print(f"Source directory: {src_dir}")
    print()

    # Step 1: Analyze code
    print("Step 1: Analyzing Python code...")
    analyzer = CodeAnalyzer(project_dir)
    modules = analyzer.analyze_directory(src_dir)
    print(f"  Found {len(modules)} modules")
    print()

    # Step 2: Build graph
    print("Step 2: Building RPG graph...")
    builder = GraphBuilder(project_dir, "py_accountant")
    root = builder.build_graph(modules)

    # Calculate metrics
    metrics = builder.calculate_metrics(root)
    print("  Metrics:")
    for key, value in metrics.items():
        print(f"    {key}: {value}")
    print()

    # Extract dependencies
    dependency_graph = builder.extract_dependency_graph(root)
    print(f"  Found {len(dependency_graph)} modules with dependencies")
    print()

    # Step 3: Write to YAML
    print("Step 3: Writing to YAML...")
    customize_yaml_dumper()
    writer = YAMLWriter("py_accountant", "1.1.0")
    writer.write_to_file(
        root,
        output_file,
        description="Async accounting ledger with Clean Architecture",
        metrics=metrics,
        dependency_graph=dependency_graph,
    )

    print(f"✓ RPG generated: {output_file}")
    print()

    # Show some example data
    print("Example: Top-level modules")
    for child in root.children[:5]:
        if child.node_type == "directory":
            print(f"  📁 {child.name}")
            # Count children
            child_count = len(child.children)
            print(f"     Contains {child_count} items")


if __name__ == "__main__":
    main()

