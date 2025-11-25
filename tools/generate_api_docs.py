#!/usr/bin/env python3
"""Генератор API документации из исходного кода.

Извлекает сигнатуры use cases, protocols и DTOs через introspection.
"""
import inspect
import importlib
import sys
from pathlib import Path
from typing import get_type_hints, Any

# Добавляем src в PYTHONPATH
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))


def extract_use_case_info(module_path: str, class_name: str) -> dict[str, Any]:
    """Извлечь информацию о use case из кода."""
    try:
        module = importlib.import_module(module_path)
        cls = getattr(module, class_name)

        # Получаем __call__ метод для dataclass use cases
        if hasattr(cls, "__call__"):
            method = cls.__call__
        else:
            return {"error": f"No __call__ method in {class_name}"}

        signature = inspect.signature(method)
        docstring = inspect.getdoc(cls) or inspect.getdoc(method) or "No docstring"

        # Извлекаем параметры
        parameters = {}
        for name, param in signature.parameters.items():
            if name == "self":
                continue
            parameters[name] = {
                "annotation": str(param.annotation) if param.annotation != inspect.Parameter.empty else "Any",
                "default": str(param.default) if param.default != inspect.Parameter.empty else None,
                "kind": str(param.kind),
            }

        return {
            "class_name": class_name,
            "module_path": module_path,
            "signature": str(signature),
            "docstring": docstring,
            "parameters": parameters,
            "return_annotation": str(signature.return_annotation) if signature.return_annotation != inspect.Signature.empty else "None",
        }
    except Exception as e:
        return {"error": str(e), "class_name": class_name, "module_path": module_path}


def extract_protocol_info(module_path: str, class_name: str) -> dict[str, Any]:
    """Извлечь информацию о protocol из кода."""
    try:
        module = importlib.import_module(module_path)
        cls = getattr(module, class_name)

        docstring = inspect.getdoc(cls) or "No docstring"

        # Извлекаем методы protocol
        methods = {}
        for name, obj in inspect.getmembers(cls):
            if name.startswith("_"):
                continue
            if inspect.isfunction(obj) or inspect.ismethod(obj):
                sig = inspect.signature(obj)
                methods[name] = {
                    "signature": str(sig),
                    "docstring": inspect.getdoc(obj) or "",
                }

        # Извлекаем properties
        properties = {}
        for name, obj in inspect.getmembers(cls):
            if isinstance(obj, property):
                properties[name] = {
                    "type": "property",
                    "docstring": inspect.getdoc(obj) or "",
                }

        return {
            "class_name": class_name,
            "module_path": module_path,
            "docstring": docstring,
            "methods": methods,
            "properties": properties,
        }
    except Exception as e:
        return {"error": str(e), "class_name": class_name, "module_path": module_path}


def extract_dto_info(module_path: str, class_name: str) -> dict[str, Any]:
    """Извлечь информацию о DTO из кода."""
    try:
        module = importlib.import_module(module_path)
        cls = getattr(module, class_name)

        docstring = inspect.getdoc(cls) or "No docstring"

        # Извлекаем поля dataclass
        fields = {}
        if hasattr(cls, "__dataclass_fields__"):
            for field_name, field_obj in cls.__dataclass_fields__.items():
                fields[field_name] = {
                    "type": str(field_obj.type),
                    "default": str(field_obj.default) if field_obj.default != inspect.Parameter.empty else None,
                    "default_factory": str(field_obj.default_factory) if field_obj.default_factory != inspect.Parameter.empty else None,
                }

        return {
            "class_name": class_name,
            "module_path": module_path,
            "docstring": docstring,
            "fields": fields,
        }
    except Exception as e:
        return {"error": str(e), "class_name": class_name, "module_path": module_path}


# Список всех async use cases
USE_CASES = [
    # currencies
    ("py_accountant.application.use_cases_async.currencies", "AsyncCreateCurrency"),
    ("py_accountant.application.use_cases_async.currencies", "AsyncSetBaseCurrency"),
    ("py_accountant.application.use_cases_async.currencies", "AsyncListCurrencies"),
    # accounts
    ("py_accountant.application.use_cases_async.accounts", "AsyncCreateAccount"),
    ("py_accountant.application.use_cases_async.accounts", "AsyncGetAccount"),
    ("py_accountant.application.use_cases_async.accounts", "AsyncListAccounts"),
    # ledger
    ("py_accountant.application.use_cases_async.ledger", "AsyncPostTransaction"),
    ("py_accountant.application.use_cases_async.ledger", "AsyncListTransactionsBetween"),
    ("py_accountant.application.use_cases_async.ledger", "AsyncGetLedger"),
    # fx_audit
    ("py_accountant.application.use_cases_async.fx_audit", "AsyncAddExchangeRateEvent"),
    ("py_accountant.application.use_cases_async.fx_audit", "AsyncListExchangeRateEvents"),
    # fx_audit_ttl
    ("py_accountant.application.use_cases_async.fx_audit_ttl", "AsyncPlanFxAuditTTL"),
    ("py_accountant.application.use_cases_async.fx_audit_ttl", "AsyncExecuteFxAuditTTL"),
    # trading_balance
    ("py_accountant.application.use_cases_async.trading_balance", "AsyncGetTradingBalanceRaw"),
    ("py_accountant.application.use_cases_async.trading_balance", "AsyncGetTradingBalanceDetailed"),
    # reporting
    ("py_accountant.application.use_cases_async.reporting", "AsyncGetParityReport"),
    ("py_accountant.application.use_cases_async.reporting", "AsyncGetTradingBalanceSnapshotReport"),
]

# Список protocols
PROTOCOLS = [
    ("py_accountant.application.ports", "Clock"),
    ("py_accountant.application.ports", "AsyncUnitOfWork"),
    ("py_accountant.application.ports", "AsyncCurrencyRepository"),
    ("py_accountant.application.ports", "AsyncAccountRepository"),
    ("py_accountant.application.ports", "AsyncTransactionRepository"),
    ("py_accountant.application.ports", "AsyncExchangeRateEventsRepository"),
]

# Список DTOs
DTOS = [
    ("py_accountant.application.dto.models", "CurrencyDTO"),
    ("py_accountant.application.dto.models", "AccountDTO"),
    ("py_accountant.application.dto.models", "EntryLineDTO"),
    ("py_accountant.application.dto.models", "TransactionDTO"),
    ("py_accountant.application.dto.models", "RichTransactionDTO"),
    ("py_accountant.application.dto.models", "ExchangeRateEventDTO"),
    ("py_accountant.application.dto.models", "TradingBalanceLineSimple"),
    ("py_accountant.application.dto.models", "TradingBalanceLineDetailed"),
    ("py_accountant.application.dto.models", "ParityLineDTO"),
    ("py_accountant.application.dto.models", "ParityReportDTO"),
    ("py_accountant.application.dto.models", "TradingBalanceSnapshotDTO"),
    ("py_accountant.application.dto.models", "FxAuditTTLPlanDTO"),
    ("py_accountant.application.dto.models", "FxAuditTTLResultDTO"),
    ("py_accountant.application.dto.models", "BatchDTO"),
]


def main():
    """Главная функция для вывода информации."""
    print("# Use Cases")
    print()
    for module_path, class_name in USE_CASES:
        info = extract_use_case_info(module_path, class_name)
        if "error" in info:
            print(f"## {class_name} - ERROR: {info['error']}")
            continue

        print(f"## {class_name}")
        print(f"**Module**: `{module_path}`")
        print(f"**Signature**: `{info['signature']}`")
        print()
        print("**Docstring**:")
        print(f"```\n{info['docstring']}\n```")
        print()
        print("**Parameters**:")
        for param_name, param_info in info['parameters'].items():
            default_str = f", default={param_info['default']}" if param_info['default'] else ""
            print(f"- `{param_name}`: {param_info['annotation']}{default_str}")
        print()
        print(f"**Returns**: `{info['return_annotation']}`")
        print()
        print("---")
        print()

    print("\n# Protocols")
    print()
    for module_path, class_name in PROTOCOLS:
        info = extract_protocol_info(module_path, class_name)
        if "error" in info:
            print(f"## {class_name} - ERROR: {info['error']}")
            continue

        print(f"## {class_name}")
        print(f"**Module**: `{module_path}`")
        print()
        print("**Docstring**:")
        print(f"```\n{info['docstring']}\n```")
        print()
        if info['methods']:
            print("**Methods**:")
            for method_name, method_info in info['methods'].items():
                print(f"- `{method_name}{method_info['signature']}`")
        if info['properties']:
            print("**Properties**:")
            for prop_name in info['properties'].keys():
                print(f"- `{prop_name}`")
        print()
        print("---")
        print()

    print("\n# DTOs")
    print()
    for module_path, class_name in DTOS:
        info = extract_dto_info(module_path, class_name)
        if "error" in info:
            print(f"## {class_name} - ERROR: {info['error']}")
            continue

        print(f"## {class_name}")
        print(f"**Module**: `{module_path}`")
        print()
        print("**Docstring**:")
        print(f"```\n{info['docstring']}\n```")
        print()
        print("**Fields**:")
        for field_name, field_info in info['fields'].items():
            default_str = ""
            if field_info['default']:
                default_str = f", default={field_info['default']}"
            elif field_info['default_factory']:
                default_str = f", default_factory={field_info['default_factory']}"
            print(f"- `{field_name}`: {field_info['type']}{default_str}")
        print()
        print("---")
        print()


if __name__ == "__main__":
    main()

