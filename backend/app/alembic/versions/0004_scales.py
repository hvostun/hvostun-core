"""Create scales.

Revision ID: 0004_scales
Revises: 0003_shelters
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.alembic.ops import created_at, updated_at, uuid_pk

revision = "0004_scales"
down_revision = "0003_shelters"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scales",
        uuid_pk(),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        created_at(),
        updated_at(),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("scales")
