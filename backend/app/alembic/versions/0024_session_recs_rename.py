"""Rename session_recomendations and recomendation_id.

Revision ID: 0024_session_recs_rename
Revises: 0023_auditor_group

Renames the table, column, indexes and constraints. Rows stay in place.
Constraint names differ between databases (named fk_* vs *_fkey), so the
rename looks up whatever still contains the old spelling.
"""

import re

import sqlalchemy as sa
from alembic import op

revision = "0024_session_recs_rename"
down_revision = "0023_auditor_group"
branch_labels = None
depends_on = None

_IDENT = re.compile(r"^[a-z_][a-z0-9_]*$")


def _quote(name: str) -> str:
    if not _IDENT.fullmatch(name):
        raise RuntimeError(f"unexpected identifier {name!r}")
    return f'"{name}"'


def _matching(table: str, kind: str, needle: str) -> list[str]:
    if kind == "constraint":
        sql = """
            SELECT con.conname
            FROM pg_constraint AS con
            JOIN pg_class AS rel ON rel.oid = con.conrelid
            JOIN pg_namespace AS nsp ON nsp.oid = rel.relnamespace
            WHERE nsp.nspname = 'public'
              AND rel.relname = :table
              AND con.conname LIKE :needle
            ORDER BY con.conname
        """
    else:
        sql = """
            SELECT idx.relname
            FROM pg_index AS ix
            JOIN pg_class AS idx ON idx.oid = ix.indexrelid
            JOIN pg_class AS rel ON rel.oid = ix.indrelid
            JOIN pg_namespace AS nsp ON nsp.oid = rel.relnamespace
            WHERE nsp.nspname = 'public'
              AND rel.relname = :table
              AND idx.relname LIKE :needle
            ORDER BY idx.relname
        """
    rows = op.get_bind().execute(
        sa.text(sql),
        {"table": table, "needle": f"%{needle}%"},
    )
    return [row[0] for row in rows]


def _apply_spelling(table: str, *, old: str, new: str) -> None:
    # Constraints first: renaming a unique or primary key also renames its index.
    for name in _matching(table, "constraint", old):
        renamed = name.replace(old, new)
        if renamed == name:
            continue
        op.execute(
            sa.text(
                f"ALTER TABLE {_quote(table)} "
                f"RENAME CONSTRAINT {_quote(name)} TO {_quote(renamed)}"
            )
        )
    for name in _matching(table, "index", old):
        renamed = name.replace(old, new)
        if renamed == name:
            continue
        op.execute(sa.text(f"ALTER INDEX {_quote(name)} RENAME TO {_quote(renamed)}"))


def upgrade() -> None:
    op.rename_table("session_recomendations", "session_recommendations")
    op.alter_column(
        "session_recommendations",
        "recomendation_id",
        new_column_name="recommendation_id",
    )
    _apply_spelling(
        "session_recommendations",
        old="recomendation",
        new="recommendation",
    )


def downgrade() -> None:
    _apply_spelling(
        "session_recommendations",
        old="recommendation",
        new="recomendation",
    )
    op.alter_column(
        "session_recommendations",
        "recommendation_id",
        new_column_name="recomendation_id",
    )
    op.rename_table("session_recommendations", "session_recomendations")
