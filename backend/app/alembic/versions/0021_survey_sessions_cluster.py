"""Add survey_sessions.cluster.

Revision ID: 0021_survey_sessions_cluster
Revises: 0020_recommendation_status
"""

import sqlalchemy as sa
from alembic import op

revision = "0021_survey_sessions_cluster"
down_revision = "0020_recommendation_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "survey_sessions",
        sa.Column("cluster", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("survey_sessions", "cluster")
