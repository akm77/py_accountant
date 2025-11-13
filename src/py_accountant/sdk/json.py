"""JSON presenter for py_accountant SDK.

Provides deterministic, JSON-safe serialization helpers:
- to_dict(obj): convert nested structures to JSON-safe forms
  Supported: dict, list/tuple, primitives, Decimal (str), datetime (UTC ISO8601 with Z)
  For dataclasses/attrs-like DTOs: convert to dict via dataclasses.asdict if possible,
  otherwise via shallow attribute extraction. Keys are kept in snake_case when DTO
  attributes use snake_case already; no aggressive renaming is performed.
- to_json(data): json.dumps with ensure_ascii=False, compact separators, stable key order.

Notes:
- Does not mutate global Decimal context.
- Naive datetimes are treated as UTC and formatted with suffix 'Z'.
"""
from __future__ import annotations

import json as _json
from dataclasses import asdict, is_dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

__all__ = ["to_dict", "to_json"]


def _is_primitive(x: Any) -> bool:
    return isinstance(x, (str, int, float, bool)) or x is None


def _serialize_datetime(dt: datetime) -> str:
    """Serialize datetime to UTC ISO8601 with trailing 'Z'. Naive -> UTC.

    Example: 2024-01-02T03:04:05Z
    """
    dt = dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)
    # Always drop microseconds for deterministic output
    dt = dt.replace(microsecond=0)
    return dt.isoformat().replace("+00:00", "Z")


def _to_mapping(obj: Any) -> dict[str, Any]:
    # Dataclasses
    if is_dataclass(obj):
        return asdict(obj)
    # Pydantic-like or simple objects with __dict__
    if hasattr(obj, "__dict__"):
        # Exclude private/dunder
        return {k: v for k, v in vars(obj).items() if not k.startswith("_")}
    # Fallback: try mapping protocol
    try:
        return dict(obj)  # type: ignore[arg-type]
    except Exception:
        # Last resort: represent as string
        return {"value": str(obj)}


def to_dict(obj: Any) -> Any:
    """Convert input to a JSON-safe structure.

    - Decimal -> str (preserve quantization)
    - datetime -> UTC ISO8601 with Z (naive assumed UTC)
    - dict/list/tuple -> recurse
    - dataclasses/objects -> mapping via asdict/vars
    """
    # Primitives
    if _is_primitive(obj):
        return obj
    # Decimal
    if isinstance(obj, Decimal):
        return str(obj)
    # datetime
    if isinstance(obj, datetime):
        return _serialize_datetime(obj)
    # list/tuple
    if isinstance(obj, (list, tuple)):
        return [to_dict(x) for x in obj]
    # dict
    if isinstance(obj, dict):
        return {str(k): to_dict(v) for k, v in obj.items()}
    # dataclass / object mapping
    mapping = _to_mapping(obj)
    return {str(k): to_dict(v) for k, v in mapping.items()}


def to_json(data: Any) -> str:
    """Dump input as deterministic JSON string using to_dict normalization."""
    return _json.dumps(to_dict(data), ensure_ascii=False, separators=(",", ":"), sort_keys=True)
