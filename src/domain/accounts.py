"""Domain Account value object.

Public API:
- Account: validated account identifier with hierarchical full name and currency code.

Constraints:
- full_name: required, trimmed, format "Segment[:Segment]*" without leading/trailing ':' or empty segments.
  Each segment is trimmed and must be 1..64 chars. Total full_name length must be <= 255.
  Max segments: 64 (guards pathological depth). Strict character set is deferred (TODO).
- currency_code: normalized to upper(), must be length 3..10.
- parent_id: optional opaque reference; not used by domain logic.

No infrastructure dependencies. Global Decimal context is not modified.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .errors import ValidationError

_MAX_FULL_NAME_LEN = 255
_MAX_SEGMENT_LEN = 64
_MAX_SEGMENTS = 64
_MIN_CURRENCY_LEN = 3
_MAX_CURRENCY_LEN = 10


def _parse_full_name(raw: str) -> tuple[str, ...]:
    """Parse and validate an account full name into segments.

    Rules implemented:
    - Trim overall string; must be non-empty after trim.
    - No leading/trailing ':'; no '::' (empty segment).
    - Split by ':'; trim each segment; each must be non-empty and 1..64 chars.
    - Total full name length must be <= 255 (after overall trim, preserving colons).
    - Number of segments must be <= 64.

    Returns:
        tuple[str, ...]: The normalized segments (trim applied per segment).

    Raises:
        ValidationError: On any format/length violation.
    """
    if raw is None:
        raise ValidationError("full_name is required")
    full = raw.strip()
    if not full:
        raise ValidationError("full_name must be a non-empty string")
    if len(full) > _MAX_FULL_NAME_LEN:
        raise ValidationError("full_name too long (max 255)")
    if full.startswith(":") or full.endswith(":"):
        raise ValidationError("full_name must not start or end with ':'")
    if "::" in full:
        # Early fail for definitely empty segment without further splitting
        raise ValidationError("full_name contains empty segment (::)")

    parts = full.split(":")
    if len(parts) > _MAX_SEGMENTS:
        raise ValidationError("too many account segments (max 64)")
    segments: list[str] = []
    for seg in parts:
        seg_t = seg.strip()
        if not seg_t:
            raise ValidationError("account segment must be non-empty after trim")
        if len(seg_t) > _MAX_SEGMENT_LEN:
            raise ValidationError("account segment too long (max 64)")
        # TODO: Enforce strict character set (letters/digits/space/_/-). Currently only non-empty + length.
        segments.append(seg_t)

    return tuple(segments)


@dataclass(slots=True)
class Account:
    """Validated account identifier with hierarchical name and currency.

    Attributes:
        full_name: Hierarchical name like "Assets:Cash:Wallet". Validated and trimmed.
        currency_code: Currency code normalized to upper case; length 3..10.
        parent_id: Optional external parent reference (not used by domain logic).

    Derived attributes:
        name: Last segment of full_name.

    Properties:
        segments: List of name segments.
        parent_path: full_name without the last segment or None for root.

    Methods:
        is_root(): True if account has a single segment (no ':').

    Notes:
        Does not touch global Decimal context. No infrastructure dependencies.
    """

    full_name: str
    currency_code: str
    parent_id: str | None = None

    # Derived/cached fields (not part of __init__ signature)
    name: str = field(init=False)
    _segments: tuple[str, ...] = field(init=False, repr=False, default=())
    _parent_path: str | None = field(init=False, repr=False, default=None)

    def __post_init__(self) -> None:
        # Validate and cache segments
        segments = _parse_full_name(self.full_name)
        self.full_name = ":".join(segments)  # normalized join (segments already trimmed)
        self._segments = segments
        self.name = segments[-1]
        self._parent_path = ":".join(segments[:-1]) if len(segments) > 1 else None

        # Normalize and validate currency_code
        cur = (self.currency_code or "").strip().upper()
        if not (_MIN_CURRENCY_LEN <= len(cur) <= _MAX_CURRENCY_LEN):
            raise ValidationError("invalid currency_code length (expected 3..10)")
        self.currency_code = cur
        # parent_id is accepted as-is (may be None)

    @property
    def segments(self) -> list[str]:
        """Return hierarchical segments of full_name as a list of strings."""
        return list(self._segments)

    @property
    def parent_path(self) -> str | None:
        """Return full_name without the last segment, or None for root accounts."""
        return self._parent_path

    def is_root(self) -> bool:
        """Return True if account has a single segment (no hierarchy)."""
        return len(self._segments) == 1

    @property
    def depth(self) -> int:
        """Depth of the account hierarchy (number of segments)."""
        return len(self._segments)
