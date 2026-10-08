"""group work

Revision ID: c0a4c54fc160
Revises: fb3021c02d01
Create Date: 2026-10-08 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'c0a4c54fc160'
down_revision = 'fb3021c02d01'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('submissions', sa.Column('is_group_work', sa.Boolean(), nullable=True))
    op.add_column('submissions', sa.Column('group_members', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.execute("UPDATE submissions SET is_group_work = FALSE WHERE is_group_work IS NULL")
    op.alter_column('submissions', 'is_group_work', nullable=False, server_default='false')


def downgrade() -> None:
    op.drop_column('submissions', 'group_members')
    op.drop_column('submissions', 'is_group_work')
