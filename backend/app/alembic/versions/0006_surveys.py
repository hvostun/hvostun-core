"""Create surveys.

Revision ID: 0006_surveys
Revises: 0005_recommendations
"""

import sqlalchemy as sa
from alembic import op

from app.alembic.ops import created_at, updated_at, uuid_pk

revision = "0006_surveys"
down_revision = "0005_recommendations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "surveys",
        uuid_pk(),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        created_at(),
        updated_at(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uq_surveys_slug"),
    )


def downgrade() -> None:
    op.drop_table("surveys")
