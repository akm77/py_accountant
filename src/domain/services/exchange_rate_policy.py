from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation


@dataclass(slots=True)
class ExchangeRatePolicy:
    """Strategy for updating exchange rates based on new observed rates.

    Modes:
    - "last_write": simply take the last seen rate (observed).
    - "weighted_average": incremental average of all observed rates:
        If first update with existing previous: new = (prev * 1 + observed) / 2
        Else: new = (prev * count_prev + observed) / (count_prev + 1)
        where count_prev tracks number of prior observations incorporated.
      Protection: if previous is None or <= 0 -> fallback to observed and reset count to 1.

    State (seen_count) is per policy instance; future iteration may track counts per currency.
    """

    mode: str = "last_write"
    seen_count: int = field(default=0, init=False)

    def apply(self, previous: Decimal | None, observed: Decimal) -> Decimal:
        if observed <= 0:
            raise ValueError("Observed rate must be > 0")
        if self.mode == "last_write" or previous is None or previous <= 0:
            self.seen_count = 1
            return observed
        if self.mode == "weighted_average":
            try:
                if self.seen_count <= 1:  # first averaging step (previous counted once)
                    new_rate = (previous + observed) / Decimal("2")
                    self.seen_count = 2
                else:
                    # previous already an average over seen_count observations
                    new_rate = (previous * Decimal(str(self.seen_count)) + observed) / Decimal(str(self.seen_count + 1))
                    self.seen_count += 1
                return new_rate
            except (InvalidOperation, ArithmeticError):  # pragma: no cover
                return observed
        return observed
