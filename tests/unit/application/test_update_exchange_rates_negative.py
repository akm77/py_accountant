from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from application.dto.models import RateUpdateInput
from application.use_cases.exchange_rates import UpdateExchangeRates
from application.use_cases.ledger import CreateCurrency
from domain import DomainError, ExchangeRatePolicy
from infrastructure.persistence.inmemory.clock import FixedClock
from infrastructure.persistence.inmemory.uow import InMemoryUnitOfWork


def _setup_uow():
    uow = InMemoryUnitOfWork()
    clock = FixedClock(datetime.now(UTC))
    return uow, clock


def test_set_base_unknown_currency_errors():
    uow, clock = _setup_uow()
    updates = [RateUpdateInput(code="USD", rate=Decimal("1.0"))]
    with pytest.raises(DomainError):
        UpdateExchangeRates(uow)(updates, set_base="EUR")  # EUR not created


def test_invalid_currency_code_length():
    uow, clock = _setup_uow()
    bad_code = "TOO_LONG_CODE"  # > 10 chars
    with pytest.raises(DomainError):
        CreateCurrency(uow)(bad_code)


def test_invalid_currency_code_empty():
    uow, clock = _setup_uow()
    with pytest.raises(DomainError):
        CreateCurrency(uow)("")


def test_zero_rate_errors():
    uow, clock = _setup_uow()
    CreateCurrency(uow)("USD")
    updates = [RateUpdateInput(code="USD", rate=Decimal("0"))]
    with pytest.raises(DomainError):
        UpdateExchangeExchangeRates = UpdateExchangeRates(uow)
        UpdateExchangeExchangeRates(updates)


def test_negative_rate_errors():
    uow, clock = _setup_uow()
    CreateCurrency(uow)("USD")
    updates = [RateUpdateInput(code="USD", rate=Decimal("-1"))]
    with pytest.raises(DomainError):
        UpdateExchangeRates(uow)(updates)


def test_weighted_average_policy_applies_and_validates():
    uow, clock = _setup_uow()
    CreateCurrency(uow)("USD")
    updates = [RateUpdateInput(code="USD", rate=Decimal("1.0"))]
    UpdateExchangeRates(uow, policy=ExchangeRatePolicy(mode="weighted_average"))(updates)
    # second update should average (1.0 + 2.0)/2 = 1.5
    updates2 = [RateUpdateInput(code="USD", rate=Decimal("2.0"))]
    UpdateExchangeRates(uow, policy=ExchangeRatePolicy(mode="weighted_average"))(updates2)
    cur = uow.currencies.get_by_code("USD")
    assert cur.exchange_rate == Decimal("1.5")

