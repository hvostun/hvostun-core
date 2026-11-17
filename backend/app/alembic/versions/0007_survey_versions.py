"""Create survey_versions.

Revision ID: 0007_survey_versions
Revises: 0006_surveys
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.alembic.ops import created_at, uuid_pk

revision = "0007_survey_versions"
down_revision = "0006_surveys"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "survey_versions",
        uuid_pk(),
        sa.Column("survey_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_num", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        created_at(),
        sa.CheckConstraint(
            "version_num > 0", name="ck_survey_versions_version_positive"
        ),
        sa.ForeignKeyConstraint(["survey_id"], ["surveys.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "survey_id",
            "version_num",
            name="uq_survey_versions_survey_version",
        ),
    )


def downgrade() -> None:
    op.drop_table("survey_versions")
