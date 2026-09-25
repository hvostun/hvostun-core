"""Create placement_events.

Revision ID: 0012_placement_events
Revises: 0011_dog_chips
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.alembic.ops import created_at, uuid_pk

revision = "0012_placement_events"
down_revision = "0011_dog_chips"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "placement_events",
        uuid_pk(),
        sa.Column("dog_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        created_at(),
        sa.ForeignKeyConstraint(["dog_id"], ["dogs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_placement_events_dog_id", "placement_events", ["dog_id"])


def downgrade() -> None:
    op.drop_index("ix_placement_events_dog_id", table_name="placement_events")
    op.drop_table("placement_events")
