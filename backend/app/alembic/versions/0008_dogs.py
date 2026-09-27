"""Create dogs.

Revision ID: 0008_dogs
Revises: 0007_survey_versions
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.alembic.ops import created_at, updated_at, uuid_pk

revision = "0008_dogs"
down_revision = "0007_survey_versions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dogs",
        uuid_pk(),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("sex", sa.Text(), nullable=True),
        sa.Column("neutered", sa.Boolean(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="unknown"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("shelter_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "assigned_volunteer_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("birthday", sa.Date(), nullable=True),
        sa.Column("status_at", sa.Date(), nullable=True),
        sa.Column("breed", sa.Text(), nullable=True),
        sa.Column("mixed", sa.Boolean(), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        created_at(),
        updated_at(),
        sa.ForeignKeyConstraint(["shelter_id"], ["shelters.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["assigned_volunteer_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["owners.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_dogs_shelter_id", "dogs", ["shelter_id"])
    op.create_index("ix_dogs_owner_id", "dogs", ["owner_id"])
    op.create_index("ix_dogs_assigned_volunteer_id", "dogs", ["assigned_volunteer_id"])
    op.create_index("ix_dogs_created_by_id", "dogs", ["created_by_id"])


def downgrade() -> None:
    op.drop_index("ix_dogs_created_by_id", table_name="dogs")
    op.drop_index("ix_dogs_assigned_volunteer_id", table_name="dogs")
    op.drop_index("ix_dogs_owner_id", table_name="dogs")
    op.drop_index("ix_dogs_shelter_id", table_name="dogs")
    op.drop_table("dogs")
