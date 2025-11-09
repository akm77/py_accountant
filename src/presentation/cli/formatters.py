from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from domain.value_objects import DomainError

__all__ = [
    "decimal_from_str",
    "dataclass_to_dict",
    "human_decimal",
]


def decimal_from_str(value: str) -> Decimal:
    try:
        d = Decimal(str(value))
    except Exception as exc:  # noqa: PERF203
        raise DomainError(f"Invalid decimal: {value}") from exc
    return d


def dataclass_to_dict(obj: Any) -> Any:
    if is_dataclass(obj):
        raw = asdict(obj)
        return {k: dataclass_to_dict(v) for k, v in raw.items()}
    if isinstance(obj, list):
        return [dataclass_to_dict(i) for i in obj]
    if isinstance(obj, dict):
        return {k: dataclass_to_dict(v) for k, v in obj.items()}
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    return obj


def human_decimal(d: Decimal | None) -> str:
    if d is None:
        return "-"
    try:
        return f"{d:.2f}"
    except Exception:  # pragma: no cover
        return str(d)
