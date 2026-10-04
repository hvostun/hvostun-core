"""Create session_recomendations.

Revision ID: 0016_session_recomendations
Revises: 0015_answer_events
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.alembic.ops import created_at, updated_at, uuid_pk

revision = "0016_session_recomendations"
down_revision = "0015_answer_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "session_recomendations",
        uuid_pk(),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("recomendation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chart_number", sa.Integer(), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        created_at(),
        updated_at(),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["session_id"], ["survey_sessions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["recomendation_id"], ["recommendations.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "session_id",
            "recomendation_id",
            name="uq_session_recomendations_user_session_recomendation",
        ),
    )
    op.create_index(
        "ix_session_recomendations_user_id",
        "session_recomendations",
        ["user_id"],
    )
    op.create_index(
        "ix_session_recomendations_session_id",
        "session_recomendations",
        ["session_id"],
    )
    op.create_index(
        "ix_session_recomendations_recomendation_id",
        "session_recomendations",
        ["recomendation_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_session_recomendations_recomendation_id",
        table_name="session_recomendations",
    )
    op.drop_index(
        "ix_session_recomendations_session_id",
        table_name="session_recomendations",
    )
    op.drop_index(
        "ix_session_recomendations_user_id",
        table_name="session_recomendations",
    )
    op.drop_table("session_recomendations")
