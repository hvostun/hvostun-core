"""Create recommendations.

Revision ID: 0005_recommendations
Revises: 0004_scales
"""

import sqlalchemy as sa
from alembic import op

from app.alembic.ops import created_at, updated_at, uuid_pk

revision = "0005_recommendations"
down_revision = "0004_scales"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "recommendations",
        uuid_pk(),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        created_at(),
        updated_at(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_recommendations_slug", "recommendations", ["slug"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_recommendations_slug", table_name="recommendations")
    op.drop_table("recommendations")
