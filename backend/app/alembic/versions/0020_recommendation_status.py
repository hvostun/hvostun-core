"""Add recommendations.status.

Revision ID: 0020_recommendation_status
Revises: 0019_moderator_group
"""

import sqlalchemy as sa
from alembic import op

revision = "0020_recommendation_status"
down_revision = "0019_moderator_group"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("recommendations")}
    if "status" not in columns:
        op.add_column(
            "recommendations",
            sa.Column("status", sa.Text(), nullable=False, server_default="active"),
        )
        op.alter_column("recommendations", "status", server_default="draft")
    constraints = {
        constraint["name"]
        for constraint in inspector.get_check_constraints("recommendations")
    }
    if "ck_recommendations_status" not in constraints:
        op.create_check_constraint(
            "ck_recommendations_status",
            "recommendations",
            "status IN ('draft', 'active', 'canceled')",
        )
    op.drop_constraint("ck_recommendations_group", "recommendations", type_="check")
    op.create_check_constraint(
        "ck_recommendations_group",
        "recommendations",
        "\"group\" IN ("
        "'Excitability', 'Aggression', 'Fear_Anxiety', 'Separation', "
        "'Attachment', 'Training', 'Miscellaneous', 'Unknown', 'other'"
        ")",
    )


def downgrade() -> None:
    op.drop_constraint("ck_recommendations_status", "recommendations", type_="check")
    op.drop_column("recommendations", "status")
    op.drop_constraint("ck_recommendations_group", "recommendations", type_="check")
    op.create_check_constraint(
        "ck_recommendations_group",
        "recommendations",
        "\"group\" IN ('other')",
    )
