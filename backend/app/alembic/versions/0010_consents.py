"""Create consents.

Revision ID: 0010_consents
Revises: 0009_questions
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.alembic.ops import uuid_pk

revision = "0010_consents"
down_revision = "0009_questions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "consents",
        uuid_pk(),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "type", "version", name="uq_consents_user_type_version"
        ),
    )


def downgrade() -> None:
    op.drop_table("consents")
