"""add account aggregate tables

Revision ID: 0008_add_account_aggregates
Revises: 0007_drop_balances_table
Create Date: 2025-11-14

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0008_add_account_aggregates'
down_revision: str | None = '0007_drop_balances_table'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # account_balances
    op.create_table(
        'account_balances',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('account_full_name', sa.String(length=1024), nullable=False, unique=True),
        sa.Column('currency_code', sa.String(length=10), nullable=False),
        sa.Column('balance', sa.Numeric(20, 6), nullable=False, server_default='0'),
        sa.Column('last_journal_id', sa.Integer(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_account_balances_full_name', 'account_balances', ['account_full_name'])

    # account_daily_turnovers
    op.create_table(
        'account_daily_turnovers',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('account_full_name', sa.String(length=1024), nullable=False),
        sa.Column('currency_code', sa.String(length=10), nullable=False),
        sa.Column('date_utc', sa.DateTime(timezone=True), nullable=False),
        sa.Column('debit_total', sa.Numeric(20, 6), nullable=False, server_default='0'),
        sa.Column('credit_total', sa.Numeric(20, 6), nullable=False, server_default='0'),
        sa.UniqueConstraint('account_full_name', 'date_utc', name='uq_turnover_account_date'),
    )
    op.create_index('ix_turnover_account_date', 'account_daily_turnovers', ['account_full_name', 'date_utc'])
    op.create_index('ix_turnover_date', 'account_daily_turnovers', ['date_utc'])



def downgrade() -> None:
    op.drop_index('ix_turnover_date', table_name='account_daily_turnovers')
    op.drop_index('ix_turnover_account_date', table_name='account_daily_turnovers')
    op.drop_table('account_daily_turnovers')
    op.drop_index('ix_account_balances_full_name', table_name='account_balances')
    op.drop_table('account_balances')

