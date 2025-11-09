"""add is_base to currencies

Revision ID: 0002_add_is_base_currency
Revises: 0001_initial
Create Date: 2025-11-09

Добавляет колонку is_base для явного указания базовой валюты.
Singleton (ровно одна) обеспечивается логикой set_base в репозитории (SQLite не поддерживает частичные индексы легко).
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0002_add_is_base_currency'
down_revision: str | None = '0001_initial'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('currencies', sa.Column('is_base', sa.Boolean(), nullable=False, server_default=sa.text('0')))
    # Normalize server default after backfilling
    with op.batch_alter_table('currencies') as batch_op:
        batch_op.alter_column('is_base', server_default=None)


def downgrade() -> None:
    # Удаляем признак базовой валюты; логика приложения должна корректно перейти в режим без base.
    with op.batch_alter_table('currencies') as batch_op:
        batch_op.drop_column('is_base')
