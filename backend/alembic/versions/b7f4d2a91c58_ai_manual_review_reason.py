"""ai manual review reason

Revision ID: b7f4d2a91c58
Revises: d5a83c1e7b40
Create Date: 2026-11-10 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b7f4d2a91c58'
down_revision = 'd5a83c1e7b40'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # AI-проверка теперь умеет отдавать работу человеку: причину пишем отдельно
    op.add_column('submissions', sa.Column('ai_review_reason', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('submissions', 'ai_review_reason')
