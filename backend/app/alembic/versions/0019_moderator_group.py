"""Allow the moderator user group.

Revision ID: 0019_moderator_group
Revises: 0018_survey_sessions_summary
"""

from alembic import op

revision = "0019_moderator_group"
down_revision = "0018_survey_sessions_summary"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_users_group", "users", type_="check")
    op.create_check_constraint(
        "ck_users_group",
        "users",
        "\"group\" IN ('admin', 'expert', 'moderator')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_users_group", "users", type_="check")
    op.create_check_constraint(
        "ck_users_group",
        "users",
        "\"group\" IN ('admin', 'expert')",
    )
