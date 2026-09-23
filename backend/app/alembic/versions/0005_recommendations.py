"""Recommendations catalog and session_recomendations.

Revision ID: 0005_recommendations
Revises: 0004_question_global_id
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005_recommendations"
down_revision = "0004_question_global_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "recommendations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_recommendations_slug", "recommendations", ["slug"], unique=True)

    op.create_table(
        "session_recomendations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("recomendation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chart_number", sa.Integer(), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["questionnaire_sessions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["recomendation_id"], ["recommendations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "session_id",
            "recomendation_id",
            name="uq_session_recomendations_user_session_recomendation",
        ),
    )
    op.create_index(
        "ix_session_recomendations_session_id",
        "session_recomendations",
        ["session_id"],
    )
    op.create_index(
        "ix_session_recomendations_user_id",
        "session_recomendations",
        ["user_id"],
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
        "ix_session_recomendations_user_id",
        table_name="session_recomendations",
    )
    op.drop_index(
        "ix_session_recomendations_session_id",
        table_name="session_recomendations",
    )
    op.drop_table("session_recomendations")
    op.drop_index("ix_recommendations_slug", table_name="recommendations")
    op.drop_table("recommendations")
