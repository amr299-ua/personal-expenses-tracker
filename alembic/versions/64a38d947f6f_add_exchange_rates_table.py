"""Add exchange_rates table.

Revision ID: 64a38d947f6f
Revises: c3c47ff3f3aa
Create Date: 2026-05-06 12:04:40.255001

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '64a38d947f6f'
down_revision: str | Sequence[str] | None = 'c3c47ff3f3aa'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "exchange_rates",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("from_currency", sa.String(length=3), nullable=False),
        sa.Column("to_currency", sa.String(length=3), nullable=False),
        sa.Column("rate", sa.Numeric(precision=15, scale=6), nullable=False),
        sa.Column("rate_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("exchange_rates", schema=None) as batch_op:
        batch_op.create_index("idx_exchange_rate_lookup", ["from_currency", "to_currency", "rate_date"])


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("exchange_rates", schema=None) as batch_op:
        batch_op.drop_index("idx_exchange_rate_lookup")
    op.drop_table("exchange_rates")
