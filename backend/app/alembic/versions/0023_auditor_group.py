"""Allow the auditor user group.

Revision ID: 0023_auditor_group
Revises: 0022_drop_rec_group_check
"""

from alembic import op

revision = "0023_auditor_group"
down_revision = "0022_drop_rec_group_check"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_users_group", "users", type_="check")
    op.create_check_constraint(
        "ck_users_group",
        "users",
        "\"group\" IN ('admin', 'expert', 'moderator', 'auditor')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_users_group", "users", type_="check")
    op.create_check_constraint(
        "ck_users_group",
        "users",
        "\"group\" IN ('admin', 'expert', 'moderator')",
    )
