"""drop balances table

Revision ID: 0007_drop_balances_table
Revises: 0006_add_journal_idempotency_key
Create Date: 2025-11-13

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa  # noqa: F401

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0007_drop_balances_table'
down_revision: str | None = '0006_add_journal_idempotency_key'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Drop balances table if it exists (SQLite/Postgres safe)
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if 'balances' in insp.get_table_names():
        op.drop_table('balances')


def downgrade() -> None:
    # Re-create balances table for downgrade (shape from 0001_initial)
    op.create_table(
        'balances',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('account_full_name', sa.String(length=1024), nullable=False),
        sa.Column('amount', sa.Numeric(20, 6), nullable=False),
        sa.Column('last_ts', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('account_full_name', name='uq_balances_account'),
    )

