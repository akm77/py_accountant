from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal

from application.dto.models import CurrencyDTO, RateUpdateInput
from application.interfaces.ports import UnitOfWork
from application.utils.quantize import rate_quantize
from domain import CurrencyCode, DomainError, ExchangeRatePolicy


@dataclass
class UpdateExchangeRates:
    uow: UnitOfWork
    policy: ExchangeRatePolicy | None = None

    def __call__(self, updates: Iterable[RateUpdateInput], set_base: str | None = None) -> None:
        # Handle base currency setting first
        if set_base:
            code = CurrencyCode(set_base).code
            existing = self.uow.currencies.get_by_code(code)
            if not existing:
                # Explicit behavior: do not auto-create base currency
                raise DomainError(f"Currency not found for set_base: {code}")
            else:
                existing.is_base = True
                self.uow.currencies.upsert(existing)
            # Ensure single base
            self.uow.currencies.set_base(code)
        # Normalize updates
        updates_list = list(updates)
        if not updates_list:
            self.uow.commit()
            return
        normalized: list[tuple[str, Decimal]] = []
        for upd in updates_list:
            code = CurrencyCode(upd.code).code
            if upd.rate is None:
                raise DomainError("Rate must be provided")
            try:
                rate = Decimal(upd.rate)
            except Exception as e:  # noqa: BLE001
                raise DomainError("Invalid rate") from e
            if rate <= 0:
                raise DomainError("Rate must be positive")
            rate = rate_quantize(rate)
            # apply policy if existing
            existing = self.uow.currencies.get_by_code(code)
            if self.policy and existing and not existing.is_base and existing.exchange_rate:
                rate = self.policy.apply(existing.exchange_rate, rate)
            normalized.append((code, rate))
        # Prefer optimized bulk path; fallback to upsert loop
        try:
            self.uow.currencies.bulk_upsert_rates(normalized)
        except Exception:
            for code, rate in normalized:
                existing = self.uow.currencies.get_by_code(code)
                dto = existing or CurrencyDTO(code=code)
                if not (dto.is_base):
                    dto.exchange_rate = rate
                self.uow.currencies.upsert(dto)
        self.uow.commit()
