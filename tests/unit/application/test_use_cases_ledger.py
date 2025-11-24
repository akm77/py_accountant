from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from py_accountant.application.dto.models import EntryLineDTO
from py_accountant.application.use_cases_async.accounts import AsyncCreateAccount
from py_accountant.application.use_cases_async.currencies import (
    AsyncCreateCurrency,
    AsyncSetBaseCurrency,
)
from py_accountant.application.use_cases_async.ledger import AsyncPostTransaction
from py_accountant.domain.errors import DomainError, ValidationError


class _TestClock:
    def now(self) -> datetime:  # minimal Clock impl
        return datetime.now(UTC)


@pytest.mark.asyncio
async def test_post_transaction_balanced_simple_usd(async_uow):
    clock = _TestClock()
    # currencies
    create_cur = AsyncCreateCurrency(async_uow)
    await create_cur("USD")
    set_base = AsyncSetBaseCurrency(async_uow)
    await set_base("USD")
    # account
    create_acc = AsyncCreateAccount(async_uow)
    await create_acc("Assets:Cash", "USD")
    post = AsyncPostTransaction(async_uow, clock)
    lines = [
        EntryLineDTO(side="DEBIT", account_full_name="Assets:Cash", amount=Decimal("100"), currency_code="USD"),
        EntryLineDTO(side="CREDIT", account_full_name="Assets:Cash", amount=Decimal("100"), currency_code="USD"),
    ]
    tx = await post(lines)
    assert tx.id.startswith("tx:")


@pytest.mark.asyncio
async def test_post_transaction_unbalanced_raises_domain_error(async_uow):
    clock = _TestClock()
    create_cur = AsyncCreateCurrency(async_uow)
    await create_cur("USD")
    set_base = AsyncSetBaseCurrency(async_uow)
    await set_base("USD")
    create_acc = AsyncCreateAccount(async_uow)
    await create_acc("Assets:Cash", "USD")
    post = AsyncPostTransaction(async_uow, clock)
    lines = [
        EntryLineDTO(side="DEBIT", account_full_name="Assets:Cash", amount=Decimal("100"), currency_code="USD"),
        EntryLineDTO(side="CREDIT", account_full_name="Assets:Cash", amount=Decimal("90"), currency_code="USD"),
    ]
    with pytest.raises(DomainError):
        await post(lines)


@pytest.mark.asyncio
async def test_post_transaction_empty_lines_raises_validation_error(async_uow):
    post = AsyncPostTransaction(async_uow, _TestClock())
    with pytest.raises(ValidationError):
        await post([])


@pytest.mark.asyncio
async def test_post_transaction_missing_account_raises_value_error(async_uow):
    # currency + base
    create_cur = AsyncCreateCurrency(async_uow)
    await create_cur("USD")
    set_base = AsyncSetBaseCurrency(async_uow)
    await set_base("USD")
    post = AsyncPostTransaction(async_uow, _TestClock())
    lines = [EntryLineDTO(side="DEBIT", account_full_name="Assets:Cash", amount=Decimal("5"), currency_code="USD")]
    with pytest.raises(ValueError):
        await post(lines)


@pytest.mark.asyncio
async def test_post_transaction_missing_currency_raises_value_error(async_uow):
    # No currency created
    post = AsyncPostTransaction(async_uow, _TestClock())
    # Need account first (but currency missing triggers early ValueError)
    create_acc = AsyncCreateAccount(async_uow)
    with pytest.raises(ValueError):  # currency missing
        await create_acc("Assets:Cash", "USD")
    lines = [EntryLineDTO(side="DEBIT", account_full_name="Assets:Cash", amount=Decimal("5"), currency_code="USD")]
    with pytest.raises(ValueError):
        await post(lines)


@pytest.mark.asyncio
@pytest.mark.parametrize("amt", [Decimal("0"), Decimal("-5")])
async def test_post_transaction_zero_or_negative_amount_validation_error(async_uow, amt):
    clock = _TestClock()
    create_cur = AsyncCreateCurrency(async_uow)
    await create_cur("USD")
    set_base = AsyncSetBaseCurrency(async_uow)
    await set_base("USD")
    create_acc = AsyncCreateAccount(async_uow)
    await create_acc("Assets:Cash", "USD")
    post = AsyncPostTransaction(async_uow, clock)
    lines = [EntryLineDTO(side="DEBIT", account_full_name="Assets:Cash", amount=amt, currency_code="USD")]
    with pytest.raises(ValidationError):
        await post(lines)


@pytest.mark.asyncio
async def test_post_transaction_invalid_side_validation_error(async_uow):
    clock = _TestClock()
    create_cur = AsyncCreateCurrency(async_uow)
    await create_cur("USD")
    set_base = AsyncSetBaseCurrency(async_uow)
    await set_base("USD")
    create_acc = AsyncCreateAccount(async_uow)
    await create_acc("Assets:Cash", "USD")
    post = AsyncPostTransaction(async_uow, clock)
    lines = [EntryLineDTO(side="X", account_full_name="Assets:Cash", amount=Decimal("5"), currency_code="USD")]
    with pytest.raises(ValidationError):
        await post(lines)


@pytest.mark.asyncio
async def test_post_transaction_unknown_currency_in_domain_validation_error(async_uow):
    # Create two currencies but omit base flag on both -> base undefined error during validation
    clock = _TestClock()
    create_cur = AsyncCreateCurrency(async_uow)
    # Create USD and EUR without setting base
    await create_cur("USD")
    await create_cur("EUR", exchange_rate=Decimal("1.1"))
    # Account in USD
    create_acc = AsyncCreateAccount(async_uow)
    await create_acc("Assets:Cash", "USD")
    post = AsyncPostTransaction(async_uow, clock)
    lines = [
        EntryLineDTO(side="DEBIT", account_full_name="Assets:Cash", amount=Decimal("100"), currency_code="USD"),
        EntryLineDTO(side="CREDIT", account_full_name="Assets:Cash", amount=Decimal("100"), currency_code="EUR"),
    ]
    # ValidationError expected because base currency not defined
    with pytest.raises(ValidationError):
        await post(lines)


@pytest.mark.asyncio
async def test_post_transaction_missing_rate_non_base_validation_error(async_uow):
    clock = _TestClock()
    create_cur = AsyncCreateCurrency(async_uow)
    await create_cur("USD")
    await create_cur("EUR")  # EUR with no exchange_rate
    set_base = AsyncSetBaseCurrency(async_uow)
    await set_base("USD")
    create_acc = AsyncCreateAccount(async_uow)
    await create_acc("Assets:Cash", "USD")
    post = AsyncPostTransaction(async_uow, clock)
    lines = [
        EntryLineDTO(side="DEBIT", account_full_name="Assets:Cash", amount=Decimal("50"), currency_code="USD"),
        EntryLineDTO(side="CREDIT", account_full_name="Assets:Cash", amount=Decimal("50"), currency_code="EUR"),
    ]
    with pytest.raises(ValidationError):  # missing rate_to_base for EUR
        await post(lines)


@pytest.mark.asyncio
async def test_post_transaction_rounding_balance_passes(async_uow):
    clock = _TestClock()
    create_cur = AsyncCreateCurrency(async_uow)
    await create_cur("USD")
    set_base = AsyncSetBaseCurrency(async_uow)
    await set_base("USD")
    create_acc = AsyncCreateAccount(async_uow)
    await create_acc("Assets:Cash", "USD")
    post = AsyncPostTransaction(async_uow, clock)
    # Values that may only balance after money_quantize (2dp)
    lines = [
        EntryLineDTO(side="DEBIT", account_full_name="Assets:Cash", amount=Decimal("100.005"), currency_code="USD"),
        EntryLineDTO(side="CREDIT", account_full_name="Assets:Cash", amount=Decimal("100.005"), currency_code="USD"),
    ]
    tx = await post(lines)
    assert tx.id.startswith("tx:")


@pytest.mark.asyncio
async def test_post_transaction_multi_currency_balanced_with_rates(async_uow):
    clock = _TestClock()
    create_cur = AsyncCreateCurrency(async_uow)
    await create_cur("USD")
    await create_cur("EUR", exchange_rate=Decimal("1.111111"))
    set_base = AsyncSetBaseCurrency(async_uow)
    await set_base("USD")
    create_acc = AsyncCreateAccount(async_uow)
    await create_acc("Assets:Cash", "USD")
    post = AsyncPostTransaction(async_uow, clock)
    # Choose amounts so after conversion and quantize they balance
    lines = [
        EntryLineDTO(side="DEBIT", account_full_name="Assets:Cash", amount=Decimal("100"), currency_code="USD"),
        EntryLineDTO(side="CREDIT", account_full_name="Assets:Cash", amount=Decimal("111.111111"), currency_code="EUR"),
    ]
    # EUR amount * rate (1.111111) ≈ 123.456789 -> not balanced with 100; adjust to balance after quantize
    # Instead pick CREDIT EUR amount matching 100 USD after conversion: 100 / 1.111111 ≈ 90.000009 -> use 90.000009
    lines = [
        EntryLineDTO(side="DEBIT", account_full_name="Assets:Cash", amount=Decimal("100"), currency_code="USD"),
        EntryLineDTO(side="CREDIT", account_full_name="Assets:Cash", amount=Decimal("90.000009"), currency_code="EUR"),
    ]
    tx = await post(lines)
    assert tx.id.startswith("tx:")

