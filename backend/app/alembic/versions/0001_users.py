"""Create users.

Revision ID: 0001_users
Revises:
"""

import sqlalchemy as sa
from alembic import op

from app.alembic.ops import created_at, updated_at, uuid_pk

revision = "0001_users"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The Compose db-roles script creates this extension as a superuser.
    # hvostun_migrator cannot run CREATE EXTENSION, so skip it when present.
    bind = op.get_bind()
    exists = bind.execute(
        sa.text("SELECT 1 FROM pg_extension WHERE extname = 'uuid-ossp'")
    ).scalar()
    if not exists:
        op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.create_table(
        "users",
        uuid_pk(),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_superuser", sa.Boolean(), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("hashed_password", sa.String(), nullable=False),
        sa.Column(
            sa.quoted_name("group", True),
            sa.String(length=255),
            nullable=False,
            server_default="expert",
        ),
        sa.Column("phone", sa.String(length=64), nullable=True),
        sa.Column("contact", sa.String(length=255), nullable=True),
        created_at(),
        updated_at(),
        sa.CheckConstraint("\"group\" IN ('admin', 'expert')", name="ck_users_group"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
    op.execute('DROP EXTENSION IF EXISTS "uuid-ossp"')
