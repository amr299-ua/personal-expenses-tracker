"""Merge heads.

Revision ID: c3c47ff3f3aa
Revises: f1a2b3c4d5e6, 69d6f5f816a8
Create Date: 2026-05-06 12:04:35.041585

"""
from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = 'c3c47ff3f3aa'
down_revision: str | Sequence[str] | None = ('f1a2b3c4d5e6', '69d6f5f816a8')
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
