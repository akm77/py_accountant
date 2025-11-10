"""Async application use cases (ASYNC-06).

Purpose:
    Provide asynchronous counterparts of existing synchronous use cases without
    modifying or deprecating the sync API. These functions/classes orchestrate
    calls to async repositories exposed by ``AsyncUnitOfWork`` while keeping
    domain/business logic minimal (delegated to repositories/services).

Contents:
    - currencies: create/list/set base
    - accounts: create/get/list
    - transactions/ledger: post/list/query balances
    - trading: aggregate trading balance
    - fx audit: basic event insertion/listing

Notes:
    Import DTOs strictly from ``application.dto.models``. All orchestration
    functions are defined with ``async def`` and require an ``AsyncUnitOfWork``.
    Synchronous paths (CLI/tests) continue to use existing sync use cases until
    ASYNC-07 introduces presentation-layer bridges.

"""

from .currencies import (
    AsyncCreateCurrency,
    AsyncSetBaseCurrency,
    AsyncListCurrencies,
)
from .accounts import (
    AsyncCreateAccount,
    AsyncGetAccount,
    AsyncListAccounts,
)
from .ledger import (
    AsyncPostTransaction,
    AsyncListTransactionsBetween,
    AsyncGetLedger,
    AsyncGetAccountBalance,
    AsyncGetTradingBalance,
)
from .fx_audit import (
    AsyncAddExchangeRateEvent,
    AsyncListExchangeRateEvents,
)

__all__ = [
    # currencies
    "AsyncCreateCurrency",
    "AsyncSetBaseCurrency",
    "AsyncListCurrencies",
    # accounts
    "AsyncCreateAccount",
    "AsyncGetAccount",
    "AsyncListAccounts",
    # ledger/transactions
    "AsyncPostTransaction",
    "AsyncListTransactionsBetween",
    "AsyncGetLedger",
    "AsyncGetAccountBalance",
    "AsyncGetTradingBalance",
    # fx audit
    "AsyncAddExchangeRateEvent",
    "AsyncListExchangeRateEvents",
]

