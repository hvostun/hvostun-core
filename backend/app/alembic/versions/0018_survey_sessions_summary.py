"""Add survey_sessions.summary.

Revision ID: 0018_survey_sessions_summary
Revises: 0017_dictionaries
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0018_survey_sessions_summary"
down_revision = "0017_dictionaries"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "survey_sessions",
        sa.Column("summary", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("survey_sessions", "summary")
