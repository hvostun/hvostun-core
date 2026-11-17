"""Create questions.

Revision ID: 0009_questions
Revises: 0008_dogs
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.alembic.ops import created_at, updated_at, uuid_pk

revision = "0009_questions"
down_revision = "0008_dogs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "questions",
        uuid_pk(),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("scale_id", postgresql.UUID(as_uuid=True), nullable=False),
        created_at(),
        updated_at(),
        sa.ForeignKeyConstraint(["scale_id"], ["scales.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_questions_scale_id", "questions", ["scale_id"])


def downgrade() -> None:
    op.drop_index("ix_questions_scale_id", table_name="questions")
    op.drop_table("questions")
