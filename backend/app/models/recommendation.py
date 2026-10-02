import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, Column, Text, UniqueConstraint
from sqlmodel import Field, SQLModel

from app.models.base import UUID_PK_KWARGS, TimestampMixin


class RecommendationGroup(StrEnum):
    OTHER = "other"


class Recommendation(TimestampMixin, SQLModel, table=True):
    __tablename__ = "recommendations"  # pyright: ignore[reportAssignmentType]
    __table_args__ = (
        CheckConstraint("\"group\" IN ('other')", name="ck_recommendations_group"),
    )

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        sa_column_kwargs=UUID_PK_KWARGS,
    )
    name: str = Field(sa_type=Text)
    slug: str = Field(unique=True, index=True, sa_type=Text)
    text: str = Field(sa_type=Text)
    description: str | None = Field(default=None, sa_type=Text)
    group: RecommendationGroup = Field(
        default=RecommendationGroup.OTHER,
        sa_column=Column(
            "group",
            Text,
            nullable=False,
            server_default="other",
        ),
    )


class RecommendationPublic(SQLModel):
    id: uuid.UUID
    name: str
    slug: str
    text: str
    description: str | None = None
    group: RecommendationGroup
    created_at: datetime
    updated_at: datetime


class RecommendationsPublic(SQLModel):
    data: list[RecommendationPublic]
    count: int


class SessionRecommendation(TimestampMixin, SQLModel, table=True):
    __tablename__ = "session_recomendations"  # pyright: ignore[reportAssignmentType]
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "session_id",
            "recomendation_id",
            name="uq_session_recomendations_user_session_recomendation",
        ),
    )

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        sa_column_kwargs=UUID_PK_KWARGS,
    )
    user_id: uuid.UUID = Field(foreign_key="users.id", ondelete="RESTRICT", index=True)
    session_id: uuid.UUID = Field(
        foreign_key="survey_sessions.id",
        ondelete="RESTRICT",
        index=True,
    )
    recomendation_id: uuid.UUID = Field(
        foreign_key="recommendations.id",
        ondelete="RESTRICT",
        index=True,
    )
    chart_number: int
    weight: float
    comment: str | None = Field(default=None, sa_type=Text)


class SessionRecommendationPublic(SQLModel):
    id: uuid.UUID
    user_id: uuid.UUID
    session_id: uuid.UUID
    recomendation_id: uuid.UUID
    chart_number: int
    weight: float
    comment: str | None = None
    created_at: datetime
    updated_at: datetime


class SessionRecommendationsPublic(SQLModel):
    data: list[SessionRecommendationPublic]
    count: int


class SessionRecommendationItemPublic(SessionRecommendationPublic):
    recommendation_name: str
    recommendation_slug: str
    recommendation_text: str


class SessionRecommendationItemsPublic(SQLModel):
    data: list[SessionRecommendationItemPublic]
    count: int
