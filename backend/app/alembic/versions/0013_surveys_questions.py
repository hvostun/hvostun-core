"""Create surveys_questions.

Revision ID: 0013_surveys_questions
Revises: 0012_placement_events
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.alembic.ops import created_at

revision = "0013_surveys_questions"
down_revision = "0012_placement_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "surveys_questions",
        sa.Column("survey_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("question_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_num", sa.Integer(), nullable=False),
        sa.Column(
            sa.quoted_name("group", True),
            sa.Text(),
            nullable=False,
            server_default="other",
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        created_at(),
        sa.ForeignKeyConstraint(
            ["survey_version_id"], ["survey_versions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["question_id"], ["questions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint(
            "survey_version_id", "question_id", name="pk_surveys_questions"
        ),
        sa.UniqueConstraint(
            "survey_version_id",
            "order_num",
            name="uq_surveys_questions_version_order",
        ),
        sa.CheckConstraint(
            "\"group\" IN ('Excitability', 'Aggression', 'Fear_Anxiety', "
            "'Separation', 'Attachment', 'Training', 'other')",
            name="ck_surveys_questions_group",
        ),
    )
    op.create_index(
        "ix_surveys_questions_question_id", "surveys_questions", ["question_id"]
    )
    op.create_index("ix_surveys_questions_user_id", "surveys_questions", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_surveys_questions_user_id", table_name="surveys_questions")
    op.drop_index("ix_surveys_questions_question_id", table_name="surveys_questions")
    op.drop_table("surveys_questions")
