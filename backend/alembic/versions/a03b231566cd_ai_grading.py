"""ai grading

Revision ID: a03b231566cd
Revises: e1138def9406
Create Date: 2026-10-10 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a03b231566cd'
down_revision = 'e1138def9406'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('assignments', sa.Column('brief_md', sa.Text(), nullable=True))

    op.add_column('submissions', sa.Column('ai_status', sa.String(), nullable=True))
    op.add_column('submissions', sa.Column('ai_grade', sa.Integer(), nullable=True))
    op.add_column('submissions', sa.Column('ai_feedback', sa.Text(), nullable=True))

    op.execute("UPDATE submissions SET ai_status = 'disabled' WHERE ai_status IS NULL")
    op.alter_column('submissions', 'ai_status', nullable=False, server_default='disabled')


def downgrade() -> None:
    op.drop_column('submissions', 'ai_feedback')
    op.drop_column('submissions', 'ai_grade')
    op.drop_column('submissions', 'ai_status')
    op.drop_column('assignments', 'brief_md')
