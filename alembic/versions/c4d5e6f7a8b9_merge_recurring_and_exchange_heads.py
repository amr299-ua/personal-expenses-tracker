"""Merge recurring/soft-delete branch with exchange_rates head.

Revision ID: c4d5e6f7a8b9
Revises: b2c3d4e5f6a7, 64a38d947f6f
Create Date: 2026-05-11 14:00:00.000000

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c4d5e6f7a8b9'
down_revision: str | Sequence[str] | None = ('b2c3d4e5f6a7', '64a38d947f6f')
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema — no-op merge."""


def downgrade() -> None:
    """Downgrade schema — no-op merge."""
