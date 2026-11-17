import uuid
from typing import Any

from sqlalchemy import Column, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.models.base import TimestampMixin


class Dictionary(TimestampMixin, SQLModel, table=True):
    __tablename__ = "dictionaries"  # pyright: ignore[reportAssignmentType]

    key: str = Field(primary_key=True, sa_type=String)
    value: Any = Field(sa_column=Column(JSONB, nullable=False))
    created_by: uuid.UUID = Field(
        foreign_key="users.id",
        ondelete="RESTRICT",
        index=True,
    )
    updated_by: uuid.UUID = Field(
        foreign_key="users.id",
        ondelete="RESTRICT",
        index=True,
    )
