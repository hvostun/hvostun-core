"""Drop the recommendations.group check constraint.

Revision ID: 0022_drop_rec_group_check
Revises: 0021_survey_sessions_cluster
"""

import sqlalchemy as sa
from alembic import op

revision = "0022_drop_rec_group_check"
down_revision = "0021_survey_sessions_cluster"
branch_labels = None
depends_on = None

_GROUP_CHECK = (
    "\"group\" IN ("
    "'Excitability', 'Aggression', 'Fear_Anxiety', 'Separation', "
    "'Attachment', 'Training', 'Miscellaneous', 'Unknown', 'other'"
    ")"
)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    names = {
        constraint["name"]
        for constraint in inspector.get_check_constraints("recommendations")
    }
    if "ck_recommendations_group" in names:
        op.drop_constraint(
            "ck_recommendations_group", "recommendations", type_="check"
        )


def downgrade() -> None:
    op.create_check_constraint(
        "ck_recommendations_group",
        "recommendations",
        _GROUP_CHECK,
    )
