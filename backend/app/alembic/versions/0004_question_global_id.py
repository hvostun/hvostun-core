"""Replace questions.global_number with global_id UUID.

Revision ID: 0004_question_global_id
Revises: 0003_owners
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004_question_global_id"
down_revision = "0003_owners"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "questions",
        sa.Column("global_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.execute("UPDATE questions SET global_id = gen_random_uuid() WHERE global_id IS NULL")
    op.alter_column(
        "questions",
        "global_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=False,
    )
    op.create_index("ix_questions_global_id", "questions", ["global_id"], unique=True)
    op.drop_column("questions", "global_number")


def downgrade() -> None:
    op.add_column(
        "questions",
        sa.Column("global_number", sa.Integer(), nullable=True),
    )
    op.execute("UPDATE questions SET global_number = 0 WHERE global_number IS NULL")
    op.alter_column(
        "questions",
        "global_number",
        existing_type=sa.Integer(),
        nullable=False,
    )
    op.drop_index("ix_questions_global_id", table_name="questions")
    op.drop_column("questions", "global_id")
