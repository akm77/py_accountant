"""add exchange_rate_events table for FX audit

Revision ID: 0004_add_exchange_rate_events
Revises: 0003_add_performance_indexes
Create Date: 2025-11-10

Adds table exchange_rate_events with indexes for code and (code, occurred_at).
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0004_add_exchange_rate_events'
down_revision: str | None = '0003_add_performance_indexes'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'exchange_rate_events',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('code', sa.String(length=10), nullable=False),
        sa.Column('rate', sa.Numeric(20, 10), nullable=False),
        sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('policy_applied', sa.String(length=64), nullable=False),
        sa.Column('source', sa.String(length=64), nullable=True),
    )
    op.create_index('ix_fx_events_code', 'exchange_rate_events', ['code'], unique=False)
    op.create_index('ix_fx_events_occurred_at', 'exchange_rate_events', ['occurred_at'], unique=False)
    op.create_index('ix_fx_events_code_occurred_at', 'exchange_rate_events', ['code', 'occurred_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_fx_events_code_occurred_at', table_name='exchange_rate_events')
    op.drop_index('ix_fx_events_occurred_at', table_name='exchange_rate_events')
    op.drop_index('ix_fx_events_code', table_name='exchange_rate_events')
    op.drop_table('exchange_rate_events')

