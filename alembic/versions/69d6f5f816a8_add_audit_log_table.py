"""add_audit_log_table

Revision ID: 69d6f5f816a8
Revises: e7934e007a74
Create Date: 2026-05-04 17:43:17.625630

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '69d6f5f816a8'
down_revision: Union[str, Sequence[str], None] = 'e7934e007a74'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("entity", sa.String(length=120), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("details", sa.Text(), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("audit_log", schema=None) as batch_op:
        batch_op.create_index("idx_audit_log_action", ["action"])
        batch_op.create_index("idx_audit_log_entity", ["entity", "entity_id"])
        batch_op.create_index("idx_audit_log_timestamp", ["timestamp"])


def downgrade() -> None:
    with op.batch_alter_table("audit_log", schema=None) as batch_op:
        batch_op.drop_index("idx_audit_log_action")
        batch_op.drop_index("idx_audit_log_entity")
        batch_op.drop_index("idx_audit_log_timestamp")
    op.drop_table("audit_log")
