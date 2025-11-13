"""add idempotency_key to journals with unique constraint

Revision ID: 0006_add_journal_idempotency_key
Revises: 0005_exchange_rate_events_archive
Create Date: 2025-11-13

Adds nullable column idempotency_key to journals and a unique constraint.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0006_add_journal_idempotency_key'
down_revision: str | None = '0005_exchange_rate_events_archive'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # SQLite requires batch mode for column add; use unique index to enforce uniqueness
    with op.batch_alter_table('journals') as batch_op:
        batch_op.add_column(sa.Column('idempotency_key', sa.String(length=255), nullable=True))
    # Create a unique index (works across SQLite/Postgres)
    op.create_index('uq_journals_idempotency_key', 'journals', ['idempotency_key'], unique=True)


def downgrade() -> None:
    # Drop unique index first, then drop column in batch for SQLite compatibility
    op.drop_index('uq_journals_idempotency_key', table_name='journals')
    with op.batch_alter_table('journals') as batch_op:
        batch_op.drop_column('idempotency_key')
