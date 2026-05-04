"""Add backup_enabled to automation_config

Revision ID: f1a2b3c4d5e6
Revises: e7934e007a74
Create Date: 2026-05-04 16:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, Sequence[str], None] = 'e7934e007a74'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('automation_config') as batch_op:
        batch_op.add_column(sa.Column('backup_enabled', sa.Boolean(), nullable=False, server_default='0'))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('automation_config') as batch_op:
        batch_op.drop_column('backup_enabled')
