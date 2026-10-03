"""single deadline

Revision ID: fb3021c02d01
Revises: 51f2b4d58c49
Create Date: 2026-10-03 11:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'fb3021c02d01'
down_revision = '51f2b4d58c49'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('assignments', sa.Column('deadline', sa.DateTime(), nullable=True))
    op.add_column('assignments', sa.Column('is_hard_deadline', sa.Boolean(), nullable=True))

    op.execute("""
        UPDATE assignments
        SET deadline = COALESCE(hard_deadline, soft_deadline),
            is_hard_deadline = CASE WHEN hard_deadline IS NOT NULL THEN TRUE ELSE FALSE END
    """)

    op.alter_column('assignments', 'is_hard_deadline', nullable=False, server_default='false')
    op.drop_column('assignments', 'soft_deadline')
    op.drop_column('assignments', 'hard_deadline')


def downgrade() -> None:
    op.add_column('assignments', sa.Column('soft_deadline', sa.DateTime(), nullable=True))
    op.add_column('assignments', sa.Column('hard_deadline', sa.DateTime(), nullable=True))

    op.execute("""
        UPDATE assignments
        SET soft_deadline = CASE WHEN is_hard_deadline = FALSE THEN deadline ELSE NULL END,
            hard_deadline = CASE WHEN is_hard_deadline = TRUE THEN deadline ELSE NULL END
    """)

    op.drop_column('assignments', 'is_hard_deadline')
    op.drop_column('assignments', 'deadline')
