"""Owners table; dogs.owner_id references owners.

Revision ID: 0003_owners
Revises: 0002_domain_schema
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003_owners"
down_revision = "0002_domain_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "owners",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=64), nullable=True),
        sa.Column("contact", sa.String(length=255), nullable=True),
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
        sa.UniqueConstraint("email", name="uq_owners_email"),
    )
    op.execute("UPDATE dogs SET owner_id = NULL")
    op.drop_constraint("dogs_owner_id_fkey", "dogs", type_="foreignkey")
    op.create_foreign_key(
        "dogs_owner_id_fkey", "dogs", "owners", ["owner_id"], ["id"]
    )


def downgrade() -> None:
    op.drop_constraint("dogs_owner_id_fkey", "dogs", type_="foreignkey")
    op.execute("UPDATE dogs SET owner_id = NULL")
    op.create_foreign_key(
        "dogs_owner_id_fkey", "dogs", "users", ["owner_id"], ["id"]
    )
    op.drop_table("owners")
