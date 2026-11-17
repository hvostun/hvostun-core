"""Create owners.

Revision ID: 0002_owners
Revises: 0001_users
"""

import sqlalchemy as sa
from alembic import op

from app.alembic.ops import created_at, updated_at, uuid_pk

revision = "0002_owners"
down_revision = "0001_users"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "owners",
        uuid_pk(),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=64), nullable=True),
        sa.Column("contact", sa.String(length=255), nullable=True),
        created_at(),
        updated_at(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", name="uq_owners_email"),
    )


def downgrade() -> None:
    op.drop_table("owners")
