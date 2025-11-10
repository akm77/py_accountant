"""create exchange_rate_events_archive table for TTL/archive

Revision ID: 0005_exchange_rate_events_archive
Revises: 0004_add_exchange_rate_events
Create Date: 2025-11-10

Adds table exchange_rate_events_archive with indexes for code and (code, occurred_at).
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0005_exchange_rate_events_archive'
down_revision: str | None = '0004_add_exchange_rate_events'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'exchange_rate_events_archive',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('source_id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(length=10), nullable=False),
        sa.Column('rate', sa.Numeric(20, 10), nullable=False),
        sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('policy_applied', sa.String(length=64), nullable=False),
        sa.Column('source', sa.String(length=64), nullable=True),
        sa.Column('archived_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_fx_events_archive_code', 'exchange_rate_events_archive', ['code'], unique=False)
    op.create_index('ix_fx_events_archive_occurred_at', 'exchange_rate_events_archive', ['occurred_at'], unique=False)
    op.create_index('ix_fx_events_archive_code_occurred_at', 'exchange_rate_events_archive', ['code', 'occurred_at'], unique=False)
    op.create_index('ix_fx_events_archive_source_id', 'exchange_rate_events_archive', ['source_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_fx_events_archive_source_id', table_name='exchange_rate_events_archive')
    op.drop_index('ix_fx_events_archive_code_occurred_at', table_name='exchange_rate_events_archive')
    op.drop_index('ix_fx_events_archive_occurred_at', table_name='exchange_rate_events_archive')
    op.drop_index('ix_fx_events_archive_code', table_name='exchange_rate_events_archive')
    op.drop_table('exchange_rate_events_archive')

