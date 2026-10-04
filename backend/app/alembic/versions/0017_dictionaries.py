"""Create dictionaries.

Revision ID: 0017_dictionaries
Revises: 0016_session_recomendations
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.alembic.ops import created_at, updated_at

revision = "0017_dictionaries"
down_revision = "0016_session_recomendations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dictionaries",
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("value", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        created_at(),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        updated_at(),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.PrimaryKeyConstraint("key"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_dictionaries_created_by", "dictionaries", ["created_by"])
    op.create_index("ix_dictionaries_updated_by", "dictionaries", ["updated_by"])


def downgrade() -> None:
    op.drop_index("ix_dictionaries_updated_by", table_name="dictionaries")
    op.drop_index("ix_dictionaries_created_by", table_name="dictionaries")
    op.drop_table("dictionaries")
