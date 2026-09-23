"""Add scales.name and scales.description.

Revision ID: 0006_scale_name_desc
Revises: 0005_recommendations
"""

import sqlalchemy as sa
from alembic import op

revision = "0006_scale_name_desc"
down_revision = "0005_recommendations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("scales", sa.Column("name", sa.Text(), nullable=True))
    op.add_column("scales", sa.Column("description", sa.Text(), nullable=True))
    op.execute("UPDATE scales SET name = 'Без названия' WHERE name IS NULL")
    op.alter_column("scales", "name", existing_type=sa.Text(), nullable=False)


def downgrade() -> None:
    op.drop_column("scales", "description")
    op.drop_column("scales", "name")
