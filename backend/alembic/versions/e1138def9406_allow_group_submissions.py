"""allow group submissions

Revision ID: e1138def9406
Revises: c0a4c54fc160
Create Date: 2026-10-08 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e1138def9406'
down_revision = 'c0a4c54fc160'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('assignments', sa.Column('allow_group_submissions', sa.Boolean(), nullable=True))
    op.execute("UPDATE assignments SET allow_group_submissions = FALSE WHERE allow_group_submissions IS NULL")
    op.alter_column('assignments', 'allow_group_submissions', nullable=False, server_default='false')


def downgrade() -> None:
    op.drop_column('assignments', 'allow_group_submissions')
