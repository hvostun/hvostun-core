"""Create survey_sessions.

Revision ID: 0014_survey_sessions
Revises: 0013_surveys_questions
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.alembic.ops import created_at, updated_at, uuid_pk

revision = "0014_survey_sessions"
down_revision = "0013_surveys_questions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "survey_sessions",
        uuid_pk(),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dog_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("survey_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="draft"),
        sa.Column(
            "client_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        created_at(),
        updated_at(),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["owners.id"],
            name="fk_survey_sessions_owner_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["dog_id"], ["dogs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["survey_version_id"], ["survey_versions.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "id", "survey_version_id", name="uq_survey_sessions_id_version"
        ),
    )
    op.create_index(
        "ix_survey_sessions_version_created",
        "survey_sessions",
        ["survey_version_id", "created_at"],
    )
    op.create_index(
        "ix_survey_sessions_owner_created",
        "survey_sessions",
        ["owner_id", "created_at"],
    )
    op.create_index(
        "ix_survey_sessions_dog_created",
        "survey_sessions",
        ["dog_id", "created_at"],
    )
    op.create_index(
        "ix_survey_sessions_status_created",
        "survey_sessions",
        ["status", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_survey_sessions_status_created", table_name="survey_sessions")
    op.drop_index("ix_survey_sessions_dog_created", table_name="survey_sessions")
    op.drop_index("ix_survey_sessions_owner_created", table_name="survey_sessions")
    op.drop_index("ix_survey_sessions_version_created", table_name="survey_sessions")
    op.drop_table("survey_sessions")
