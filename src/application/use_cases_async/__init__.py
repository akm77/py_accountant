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
    - fx audit: basic event insertion/listing + TTL planning/execution (I19)

Notes:
    Import DTOs strictly from ``application.dto.models``. All orchestration
    functions are defined with ``async def`` and require an ``AsyncUnitOfWork``.
    Synchronous paths (CLI/tests) continue to use existing sync use cases until
    ASYNC-07 introduces presentation-layer bridges.

"""

from .accounts import (
    AsyncCreateAccount,
    AsyncGetAccount,
    AsyncListAccounts,
)
from .currencies import (
    AsyncCreateCurrency,
    AsyncListCurrencies,
    AsyncSetBaseCurrency,
)
from .fx_audit import (
    AsyncAddExchangeRateEvent,
    AsyncListExchangeRateEvents,
)
from .fx_audit_ttl import (
    AsyncExecuteFxAuditTTL,
    AsyncPlanFxAuditTTL,
)
from .ledger import (
    AsyncGetAccountBalance,
    AsyncGetLedger,
    AsyncGetTradingBalance,
    AsyncListTransactionsBetween,
    AsyncPostTransaction,
)
from .trading_balance import (
    AsyncGetTradingBalanceDetailed,
    AsyncGetTradingBalanceRaw,
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
    # new trading balance refactored use cases (I18)
    "AsyncGetTradingBalanceRaw",
    "AsyncGetTradingBalanceDetailed",
    # fx audit
    "AsyncAddExchangeRateEvent",
    "AsyncListExchangeRateEvents",
    # fx audit TTL (I19)
    "AsyncPlanFxAuditTTL",
    "AsyncExecuteFxAuditTTL",
]
