"""add performance indexes for ledger queries

Revision ID: 0003_add_performance_indexes
Revises: 0002_add_is_base_currency
Create Date: 2025-11-10

Adds indexes on journals(occurred_at), transaction_lines(account_full_name, currency_code),
composite (account_full_name, journal_id) to speed up ledger listing and balances.
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0003_add_performance_indexes'
down_revision: str | None = '0002_add_is_base_currency'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index('ix_journals_occurred_at', 'journals', ['occurred_at'], unique=False)
    op.create_index('ix_tx_lines_account_full_name', 'transaction_lines', ['account_full_name'], unique=False)
    op.create_index('ix_tx_lines_currency_code', 'transaction_lines', ['currency_code'], unique=False)
    op.create_index('ix_tx_lines_account_journal', 'transaction_lines', ['account_full_name', 'journal_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_tx_lines_account_journal', table_name='transaction_lines')
    op.drop_index('ix_tx_lines_currency_code', table_name='transaction_lines')
    op.drop_index('ix_tx_lines_account_full_name', table_name='transaction_lines')
    op.drop_index('ix_journals_occurred_at', table_name='journals')

