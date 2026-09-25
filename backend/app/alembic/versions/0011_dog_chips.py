"""Create dog_chips.

Revision ID: 0011_dog_chips
Revises: 0010_consents
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.alembic.ops import created_at, uuid_pk

revision = "0011_dog_chips"
down_revision = "0010_consents"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dog_chips",
        uuid_pk(),
        sa.Column("dog_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("system", sa.Text(), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        created_at(),
        sa.ForeignKeyConstraint(["dog_id"], ["dogs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_dog_chips_dog_id", "dog_chips", ["dog_id"])


def downgrade() -> None:
    op.drop_index("ix_dog_chips_dog_id", table_name="dog_chips")
    op.drop_table("dog_chips")
