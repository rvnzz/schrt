"""auto-added students from submissions

Revision ID: 9d1e4b7a2c53
Revises: a03b231566cd
Create Date: 2026-11-04 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9d1e4b7a2c53'
down_revision = 'a03b231566cd'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('students', sa.Column('is_auto_added', sa.Boolean(), nullable=True))
    op.execute("UPDATE students SET is_auto_added = FALSE WHERE is_auto_added IS NULL")
    op.alter_column('students', 'is_auto_added', nullable=False, server_default='false')


def downgrade() -> None:
    op.drop_column('students', 'is_auto_added')
