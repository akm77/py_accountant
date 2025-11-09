"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2025-11-09

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # currencies
    op.create_table(
        'currencies',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('code', sa.String(length=10), nullable=False, unique=True),
        sa.Column('exchange_rate', sa.Numeric(20, 10), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    # accounts
    op.create_table(
        'accounts',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=1024), nullable=False, unique=True),
        sa.Column('currency_code', sa.String(length=10), nullable=False),
        sa.Column('parent_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    # journals
    op.create_table(
        'journals',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('occurred_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('memo', sa.String(length=1024), nullable=True),
        sa.Column('meta', sa.JSON(), nullable=True),
    )
    # transaction_lines
    op.create_table(
        'transaction_lines',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('journal_id', sa.Integer(), nullable=False),
        sa.Column('account_full_name', sa.String(length=1024), nullable=False),
        sa.Column('side', sa.String(length=6), nullable=False),
        sa.Column('amount', sa.Numeric(20, 6), nullable=False),
        sa.Column('currency_code', sa.String(length=10), nullable=False),
        sa.Column('exchange_rate', sa.Numeric(20, 10), nullable=True),
    )
    # balances
    op.create_table(
        'balances',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('account_full_name', sa.String(length=1024), nullable=False),
        sa.Column('amount', sa.Numeric(20, 6), nullable=False),
        sa.Column('last_ts', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('account_full_name', name='uq_balances_account'),
    )


def downgrade() -> None:
    op.drop_table('balances')
    op.drop_table('transaction_lines')
    op.drop_table('journals')
    op.drop_table('accounts')
    op.drop_table('currencies')

