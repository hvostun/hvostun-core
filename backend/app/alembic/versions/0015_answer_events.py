"""Create answer_events.

Revision ID: 0015_answer_events
Revises: 0014_survey_sessions
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.alembic.ops import created_at, uuid_pk

revision = "0015_answer_events"
down_revision = "0014_survey_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "answer_events",
        uuid_pk(),
        sa.Column("surveys_session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("survey_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("question_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        created_at(),
        sa.ForeignKeyConstraint(
            ["surveys_session_id", "survey_version_id"],
            ["survey_sessions.id", "survey_sessions.survey_version_id"],
            name="fk_answer_events_session_version",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["survey_version_id", "question_id"],
            [
                "surveys_questions.survey_version_id",
                "surveys_questions.question_id",
            ],
            name="fk_answer_events_version_question",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_answer_events_session_question_created",
        "answer_events",
        ["surveys_session_id", "question_id", "created_at"],
    )
    op.create_index(
        "ix_answer_events_session_version",
        "answer_events",
        ["surveys_session_id", "survey_version_id"],
    )
    op.create_index(
        "ix_answer_events_version_question",
        "answer_events",
        ["survey_version_id", "question_id"],
    )
    op.create_index("ix_answer_events_question_id", "answer_events", ["question_id"])


def downgrade() -> None:
    op.drop_index("ix_answer_events_question_id", table_name="answer_events")
    op.drop_index("ix_answer_events_version_question", table_name="answer_events")
    op.drop_index("ix_answer_events_session_version", table_name="answer_events")
    op.drop_index(
        "ix_answer_events_session_question_created", table_name="answer_events"
    )
    op.drop_table("answer_events")
