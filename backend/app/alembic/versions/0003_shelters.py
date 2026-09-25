"""Create shelters.

Revision ID: 0003_shelters
Revises: 0002_owners
"""

import sqlalchemy as sa
from alembic import op

from app.alembic.ops import created_at, updated_at, uuid_pk

revision = "0003_shelters"
down_revision = "0002_owners"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "shelters",
        uuid_pk(),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("contact_info", sa.Text(), nullable=True),
        created_at(),
        updated_at(),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("shelters")
