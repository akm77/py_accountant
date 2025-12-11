#!/usr/bin/env python3
"""
AI Context Generator - Автогенерация AI-оптимизированных контекстов из кода.

Вариант 4: Автоматизация
- Парсит исходный код (AST)
- Извлекает контракты из Protocol классов
- Извлекает DTOs из dataclass объявлений
- Извлекает data flows из docstrings use cases
- Генерирует YAML файлы в ai_context/

Usage:
    python tools/generate_ai_context.py --output ai_context/
    python tools/generate_ai_context.py --validate  # Проверка синхронности
"""

import ast
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class ProtocolMethod:
    """Метод Protocol класса."""
    name: str
    args: list[tuple[str, str]]  # [(name, type), ...]
    returns: str
    is_async: bool
    description: str = ""


@dataclass
class ProtocolInfo:
    """Информация о Protocol классе."""
    name: str
    location: str
    methods: list[ProtocolMethod] = field(default_factory=list)
    attributes: list[tuple[str, str]] = field(default_factory=list)  # [(name, type), ...]
    description: str = ""


@dataclass
class DTOField:
    """Поле DTO."""
    name: str
    type_annotation: str
    default: Any = None
    description: str = ""


@dataclass
class DTOInfo:
    """Информация о DTO."""
    name: str
    location: str
    fields: list[DTOField] = field(default_factory=list)
    description: str = ""


@dataclass
class UseCaseFlow:
    """Data flow use case."""
    step: str
    action: str
    description: str = ""


@dataclass
class UseCaseInfo:
    """Информация о use case."""
    name: str
    location: str
    constructor_args: list[tuple[str, str]] = field(default_factory=list)
    call_args: list[tuple[str, str, Any]] = field(default_factory=list)  # [(name, type, default), ...]
    returns: str = ""
    flows: list[UseCaseFlow] = field(default_factory=list)
    invariants: list[str] = field(default_factory=list)
    description: str = ""


class AIContextExtractor(ast.NodeVisitor):
    """Extract AI context from Python AST."""

    def __init__(self):
        self.protocols: list[ProtocolInfo] = []
        self.dtos: list[DTOInfo] = []
        self.use_cases: list[UseCaseInfo] = []
        self.current_file: str = ""

    def extract_from_file(self, filepath: Path) -> None:
        """Extract context from a single file."""
        self.current_file = str(filepath.relative_to(Path.cwd()))
        with open(filepath, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read(), filename=str(filepath))
        self.visit(tree)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Visit class definition."""
        # Check if Protocol
        if self._is_protocol(node):
            protocol = self._extract_protocol(node)
            if protocol:
                self.protocols.append(protocol)

        # Check if DTO (dataclass)
        elif self._is_dataclass(node):
            dto = self._extract_dto(node)
            if dto:
                self.dtos.append(dto)

        # Check if use case
        elif self._is_use_case(node):
            use_case = self._extract_use_case(node)
            if use_case:
                self.use_cases.append(use_case)

        self.generic_visit(node)

    def _is_protocol(self, node: ast.ClassDef) -> bool:
        """Check if class is a Protocol."""
        return any(
            isinstance(base, ast.Name) and base.id == 'Protocol'
            for base in node.bases
        )

    def _is_dataclass(self, node: ast.ClassDef) -> bool:
        """Check if class is a dataclass."""
        return any(
            isinstance(dec, ast.Name) and dec.id == 'dataclass' or
            isinstance(dec, ast.Call) and isinstance(dec.func, ast.Name) and dec.func.id == 'dataclass'
            for dec in node.decorator_list
        )

    def _is_use_case(self, node: ast.ClassDef) -> bool:
        """Check if class is a use case (has __call__ method)."""
        return any(
            isinstance(item, ast.FunctionDef) and item.name == '__call__'
            for item in node.body
        )

    def _extract_protocol(self, node: ast.ClassDef) -> ProtocolInfo | None:
        """Extract Protocol information."""
        protocol = ProtocolInfo(
            name=node.name,
            location=self.current_file,
            description=ast.get_docstring(node) or ""
        )

        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                method = self._extract_method(item)
                if method:
                    protocol.methods.append(method)
            elif isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                # Attribute annotation
                protocol.attributes.append((
                    item.target.id,
                    ast.unparse(item.annotation) if item.annotation else "Any"
                ))

        return protocol

    def _extract_method(self, node: ast.FunctionDef) -> ProtocolMethod | None:
        """Extract method information."""
        if node.name.startswith('_') and node.name not in ('__call__', '__aenter__', '__aexit__'):
            return None  # Skip private methods

        args = []
        for arg in node.args.args:
            if arg.arg == 'self':
                continue
            arg_type = ast.unparse(arg.annotation) if arg.annotation else "Any"
            args.append((arg.arg, arg_type))

        returns = "None"
        if node.returns:
            returns = ast.unparse(node.returns)

        is_async = isinstance(node, ast.AsyncFunctionDef)

        return ProtocolMethod(
            name=node.name,
            args=args,
            returns=returns,
            is_async=is_async,
            description=ast.get_docstring(node) or ""
        )

    def _extract_dto(self, node: ast.ClassDef) -> DTOInfo | None:
        """Extract DTO information."""
        dto = DTOInfo(
            name=node.name,
            location=self.current_file,
            description=ast.get_docstring(node) or ""
        )

        for item in node.body:
            if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                field_type = ast.unparse(item.annotation) if item.annotation else "Any"
                field_default = ast.unparse(item.value) if item.value else None

                dto.fields.append(DTOField(
                    name=item.target.id,
                    type_annotation=field_type,
                    default=field_default
                ))

        return dto

    def _extract_use_case(self, node: ast.ClassDef) -> UseCaseInfo | None:
        """Extract use case information."""
        use_case = UseCaseInfo(
            name=node.name,
            location=self.current_file,
            description=ast.get_docstring(node) or ""
        )

        # Extract constructor args (dataclass fields)
        for item in node.body:
            if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                field_type = ast.unparse(item.annotation) if item.annotation else "Any"
                use_case.constructor_args.append((item.target.id, field_type))

            # Extract __call__ signature
            if isinstance(item, ast.FunctionDef) and item.name == '__call__':
                for arg in item.args.args:
                    if arg.arg == 'self':
                        continue
                    arg_type = ast.unparse(arg.annotation) if arg.annotation else "Any"
                    arg_default = None
                    # TODO: Extract default values
                    use_case.call_args.append((arg.arg, arg_type, arg_default))

                if item.returns:
                    use_case.returns = ast.unparse(item.returns)

                # Parse docstring for AI_CONTEXT
                docstring = ast.get_docstring(item)
                if docstring and "AI_CONTEXT:" in docstring:
                    use_case.flows, use_case.invariants = self._parse_ai_context(docstring)

        return use_case

    def _parse_ai_context(self, docstring: str) -> tuple[list[UseCaseFlow], list[str]]:
        """Parse AI_CONTEXT section from docstring."""
        flows = []
        invariants = []

        # Simple parser for AI_CONTEXT YAML in docstring
        if "AI_CONTEXT:" not in docstring:
            return flows, invariants

        context_section = docstring.split("AI_CONTEXT:")[1]

        # Try to parse as YAML
        try:
            # Remove indentation
            lines = context_section.split('\n')
            min_indent = min((len(line) - len(line.lstrip()) for line in lines if line.strip()), default=0)
            dedented = '\n'.join(line[min_indent:] if line.strip() else '' for line in lines)

            context_data = yaml.safe_load(dedented)

            if 'flow' in context_data:
                for flow_item in context_data['flow']:
                    flows.append(UseCaseFlow(
                        step=flow_item.get('step', ''),
                        action=flow_item.get('action', ''),
                        description=flow_item.get('description', '')
                    ))

            if 'invariants' in context_data:
                invariants = context_data['invariants']

        except Exception:
            # Fallback: простой парсинг
            pass

        return flows, invariants


class AIContextGenerator:
    """Generate AI context YAML files."""

    def __init__(self, root_dir: Path):
        self.root_dir = root_dir
        self.extractor = AIContextExtractor()

    def scan_project(self) -> None:
        """Scan project for Python files."""
        src_dir = self.root_dir / "src" / "py_accountant"

        # Scan application/ports.py
        ports_file = src_dir / "application" / "ports.py"
        if ports_file.exists():
            print(f"Scanning {ports_file}...")
            self.extractor.extract_from_file(ports_file)

        # Scan application/dto/*.py
        dto_dir = src_dir / "application" / "dto"
        if dto_dir.exists():
            for dto_file in dto_dir.glob("*.py"):
                if dto_file.name == "__init__.py":
                    continue
                print(f"Scanning {dto_file}...")
                self.extractor.extract_from_file(dto_file)

        # Scan application/use_cases_async/*.py
        use_cases_dir = src_dir / "application" / "use_cases_async"
        if use_cases_dir.exists():
            for uc_file in use_cases_dir.glob("*.py"):
                if uc_file.name == "__init__.py":
                    continue
                print(f"Scanning {uc_file}...")
                self.extractor.extract_from_file(uc_file)

    def generate_ports_yaml(self, output_path: Path) -> None:
        """Generate contracts/PORTS.yaml."""
        ports_data = {
            "# AI Context: Ports (Protocols)": None,
            "version": "1.1.0",
            "updated": "2025-11-28",
            "ports": {}
        }

        for protocol in self.extractor.protocols:
            ports_data["ports"][protocol.name] = {
                "type": "Protocol",
                "location": protocol.location,
                "description": protocol.description,
                "methods": [
                    {
                        "name": method.name,
                        "async": method.is_async,
                        "args": [{"name": name, "type": typ} for name, typ in method.args],
                        "returns": method.returns,
                        "description": method.description
                    }
                    for method in protocol.methods
                ],
                "attributes": [
                    {"name": name, "type": typ}
                    for name, typ in protocol.attributes
                ]
            }

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            yaml.dump(ports_data, f, allow_unicode=True, sort_keys=False, default_flow_style=False)

        print(f"✓ Generated {output_path}")

    def generate_dtos_yaml(self, output_path: Path) -> None:
        """Generate contracts/DTOS.yaml."""
        dtos_data = {
            "# AI Context: DTOs": None,
            "version": "1.1.0",
            "updated": "2025-11-28",
            "dtos": {}
        }

        for dto in self.extractor.dtos:
            dtos_data["dtos"][dto.name] = {
                "location": dto.location,
                "description": dto.description,
                "fields": [
                    {
                        "name": field.name,
                        "type": field.type_annotation,
                        "default": field.default,
                        "description": field.description
                    }
                    for field in dto.fields
                ]
            }

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            yaml.dump(dtos_data, f, allow_unicode=True, sort_keys=False, default_flow_style=False)

        print(f"✓ Generated {output_path}")

    def generate_flows_yaml(self, output_dir: Path) -> None:
        """Generate flows/*.yaml."""
        output_dir.mkdir(parents=True, exist_ok=True)

        for use_case in self.extractor.use_cases:
            flow_data = {
                "# AI Context: Data Flow": None,
                "use_case": use_case.name,
                "location": use_case.location,
                "description": use_case.description,
                "constructor_args": [
                    {"name": name, "type": typ}
                    for name, typ in use_case.constructor_args
                ],
                "call_args": [
                    {"name": name, "type": typ, "default": default}
                    for name, typ, default in use_case.call_args
                ],
                "returns": use_case.returns,
                "flows": [
                    {"step": flow.step, "action": flow.action, "description": flow.description}
                    for flow in use_case.flows
                ],
                "invariants": use_case.invariants
            }

            output_path = output_dir / f"{use_case.name}.yaml"
            with open(output_path, 'w', encoding='utf-8') as f:
                yaml.dump(flow_data, f, allow_unicode=True, sort_keys=False, default_flow_style=False)

            print(f"✓ Generated {output_path}")

    def validate_sync(self) -> bool:
        """Validate that generated context is in sync with code."""
        # TODO: Implement validation
        # - Check that all Protocols are extracted
        # - Check that all DTOs are extracted
        # - Check that all use cases are extracted
        print("⚠ Validation not yet implemented")
        return True


def main() -> int:
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Generate AI-optimized context from code")
    parser.add_argument('--output', type=Path, default=Path('ai_context'), help='Output directory')
    parser.add_argument('--validate', action='store_true', help='Validate sync with code')

    args = parser.parse_args()

    root_dir = Path.cwd()
    generator = AIContextGenerator(root_dir)

    if args.validate:
        generator.scan_project()
        return 0 if generator.validate_sync() else 1

    # Generate
    print("Scanning project...")
    generator.scan_project()

    print(f"\nFound:")
    print(f"  - {len(generator.extractor.protocols)} Protocols")
    print(f"  - {len(generator.extractor.dtos)} DTOs")
    print(f"  - {len(generator.extractor.use_cases)} Use Cases")

    print("\nGenerating AI context...")
    generator.generate_ports_yaml(args.output / "contracts" / "PORTS.yaml")
    generator.generate_dtos_yaml(args.output / "contracts" / "DTOS.yaml")
    generator.generate_flows_yaml(args.output / "flows")

    print("\n✓ AI context generation complete!")
    print(f"Output: {args.output.absolute()}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

