"""ai grading diagnostics

Revision ID: d5a83c1e7b40
Revises: 9d1e4b7a2c53
Create Date: 2026-11-06 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd5a83c1e7b40'
down_revision = '9d1e4b7a2c53'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('submissions', sa.Column('ai_error', sa.Text(), nullable=True))
    op.add_column('submissions', sa.Column('ai_checked_at', sa.DateTime(), nullable=True))
    op.add_column('submissions', sa.Column('ai_attempts', sa.Integer(), nullable=True))

    # Причина отказа у старых строк жила в ai_feedback — переносим её в ai_error
    op.execute(
        """
        UPDATE submissions
        SET ai_error = ai_feedback
        WHERE ai_status = 'error' AND ai_error IS NULL
        """
    )
    op.execute("UPDATE submissions SET ai_attempts = 0 WHERE ai_attempts IS NULL")
    op.alter_column('submissions', 'ai_attempts', nullable=False, server_default='0')


def downgrade() -> None:
    op.drop_column('submissions', 'ai_attempts')
    op.drop_column('submissions', 'ai_checked_at')
    op.drop_column('submissions', 'ai_error')
