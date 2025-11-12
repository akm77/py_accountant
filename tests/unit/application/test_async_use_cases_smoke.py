from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from application.dto.models import EntryLineDTO
from application.use_cases_async import (
    AsyncCreateAccount,
    AsyncCreateCurrency,
    AsyncPostTransaction,
    AsyncSetBaseCurrency,
)
from domain.errors import ValidationError


class _TestClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


@pytest.mark.asyncio
async def test_async_set_base_missing_currency_raises(async_uow):
    set_base = AsyncSetBaseCurrency(async_uow)
    with pytest.raises((ValidationError, ValueError)):
        await set_base("NOPE")


@pytest.mark.asyncio
async def test_async_create_account_missing_currency(async_uow):
    create_acc = AsyncCreateAccount(async_uow)
    with pytest.raises(ValueError):
        await create_acc("Assets:Cash", "NOPE")


@pytest.mark.asyncio
async def test_async_post_transaction_missing_account(async_uow):

    create_cur = AsyncCreateCurrency(async_uow)
    await create_cur("USD")
    post_tx = AsyncPostTransaction(async_uow, _TestClock())
    lines = [EntryLineDTO(side="DEBIT", account_full_name="Assets:Cash", amount=Decimal("5"), currency_code="USD")]
    with pytest.raises(ValueError):
        await post_tx(lines)
