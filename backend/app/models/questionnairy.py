import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator, model_validator
from sqlalchemy import (
    CheckConstraint,
    Column,
    ForeignKeyConstraint,
    Index,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.models.base import UUID_PK_KWARGS, CreatedAtMixin, TimestampMixin


class SessionStatus(StrEnum):
    DRAFT = "draft"
    FINISHED = "finished"
    CANCELED = "canceled"


class ScaleType(StrEnum):
    INTEGER = "integer"
    TEXT = "text"
    DATE = "date"


class ScaleConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min_value: int | None = None
    max_value: int | None = None
    legend: dict[str, str] | None = None

    @field_validator("legend", mode="before")
    @classmethod
    def normalize_legend(cls, value: object) -> object:
        if value is None:
            return None
        if not isinstance(value, dict):
            raise ValueError("legend must be an object")
        normalized = {str(key): str(label).strip() for key, label in value.items()}
        if any(not label for label in normalized.values()):
            raise ValueError("legend labels must not be empty")
        return normalized

    @model_validator(mode="after")
    def validate_range(self) -> ScaleConfig:
        if (
            self.min_value is not None
            and self.max_value is not None
            and self.min_value > self.max_value
        ):
            raise ValueError("min_value must not exceed max_value")
        return self


class AnswerValue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: int | str | None


class Survey(TimestampMixin, SQLModel, table=True):
    __tablename__ = "surveys"  # pyright: ignore[reportAssignmentType]

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        sa_column_kwargs=UUID_PK_KWARGS,
    )
    name: str = Field(sa_type=Text)
    slug: str = Field(unique=True, sa_type=Text)
    description: str | None = Field(default=None, sa_type=Text)


class SurveyPublic(SQLModel):
    id: uuid.UUID
    name: str
    slug: str
    description: str | None = None
    created_at: datetime
    updated_at: datetime


class SurveysPublic(SQLModel):
    data: list[SurveyPublic]
    count: int


class SurveyVersion(CreatedAtMixin, SQLModel, table=True):
    __tablename__ = "survey_versions"  # pyright: ignore[reportAssignmentType]
    __table_args__ = (
        CheckConstraint("version_num > 0", name="ck_survey_versions_version_positive"),
        UniqueConstraint(
            "survey_id",
            "version_num",
            name="uq_survey_versions_survey_version",
        ),
    )

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        sa_column_kwargs=UUID_PK_KWARGS,
    )
    survey_id: uuid.UUID = Field(foreign_key="surveys.id", ondelete="RESTRICT")
    version_num: int
    description: str | None = Field(default=None, sa_type=Text)


class SurveyVersionPublic(SQLModel):
    id: uuid.UUID
    survey_id: uuid.UUID
    version_num: int
    description: str | None = None
    created_at: datetime


class SurveyVersionsPublic(SQLModel):
    data: list[SurveyVersionPublic]
    count: int


class Scale(TimestampMixin, SQLModel, table=True):
    __tablename__ = "scales"  # pyright: ignore[reportAssignmentType]

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        sa_column_kwargs=UUID_PK_KWARGS,
    )
    name: str = Field(sa_type=Text)
    description: str | None = Field(default=None, sa_type=Text)
    type: ScaleType = Field(sa_type=Text)
    config: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(JSONB, nullable=True),
    )


class SurveyQuestion(CreatedAtMixin, SQLModel, table=True):
    __tablename__ = "surveys_questions"  # pyright: ignore[reportAssignmentType]
    __table_args__ = (
        UniqueConstraint(
            "survey_version_id",
            "order_num",
            name="uq_surveys_questions_version_order",
        ),
        Index("ix_surveys_questions_question_id", "question_id"),
        Index("ix_surveys_questions_user_id", "user_id"),
    )

    survey_version_id: uuid.UUID = Field(
        foreign_key="survey_versions.id",
        primary_key=True,
        ondelete="RESTRICT",
    )
    question_id: uuid.UUID = Field(
        foreign_key="questions.id",
        primary_key=True,
        ondelete="RESTRICT",
    )
    order_num: int
    user_id: uuid.UUID | None = Field(
        default=None, foreign_key="users.id", ondelete="RESTRICT"
    )


class Question(TimestampMixin, SQLModel, table=True):
    __tablename__ = "questions"  # pyright: ignore[reportAssignmentType]
    __table_args__ = (Index("ix_questions_scale_id", "scale_id"),)

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        sa_column_kwargs=UUID_PK_KWARGS,
    )
    global_id: uuid.UUID = Field(default_factory=uuid.uuid4, unique=True, index=True)
    text: str = Field(sa_type=Text)
    scale_id: uuid.UUID = Field(foreign_key="scales.id", ondelete="RESTRICT")


class QuestionPublic(SQLModel):
    id: uuid.UUID
    survey_version_id: uuid.UUID
    global_id: uuid.UUID
    order_number: int
    text: str
    scale_id: uuid.UUID
    scale_name: str
    created_at: datetime
    updated_at: datetime


class QuestionsPublic(SQLModel):
    data: list[QuestionPublic]
    count: int


class SurveySession(TimestampMixin, SQLModel, table=True):
    __tablename__ = "survey_sessions"  # pyright: ignore[reportAssignmentType]
    __table_args__ = (
        UniqueConstraint(
            "id",
            "survey_version_id",
            name="uq_survey_sessions_id_version",
        ),
        Index(
            "ix_survey_sessions_version_created",
            "survey_version_id",
            "created_at",
        ),
        Index("ix_survey_sessions_owner_created", "owner_id", "created_at"),
        Index("ix_survey_sessions_dog_created", "dog_id", "created_at"),
        Index("ix_survey_sessions_status_created", "status", "created_at"),
    )

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        sa_column_kwargs=UUID_PK_KWARGS,
    )
    owner_id: uuid.UUID = Field(foreign_key="users.id", ondelete="RESTRICT")
    dog_id: uuid.UUID = Field(foreign_key="dogs.id", ondelete="RESTRICT")
    survey_version_id: uuid.UUID = Field(
        foreign_key="survey_versions.id", ondelete="RESTRICT"
    )
    status: SessionStatus = Field(default=SessionStatus.DRAFT, sa_type=Text)
    client_metadata: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(JSONB, nullable=True),
    )


class SurveySessionPublic(SQLModel):
    id: uuid.UUID
    owner_id: uuid.UUID
    dog_id: uuid.UUID
    survey_version_id: uuid.UUID
    status: SessionStatus
    client_metadata: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class SurveySessionsPublic(SQLModel):
    data: list[SurveySessionPublic]
    count: int


class SessionAnswerPublic(SQLModel):
    question_id: uuid.UUID
    order_number: int
    question_text: str
    value: Any | None = None
    answered_at: datetime | None = None


class SessionAnswersPublic(SQLModel):
    data: list[SessionAnswerPublic]
    count: int


class AnswerEvent(CreatedAtMixin, SQLModel, table=True):
    __tablename__ = "answer_events"  # pyright: ignore[reportAssignmentType]
    __table_args__ = (
        ForeignKeyConstraint(
            ["surveys_session_id", "survey_version_id"],
            ["survey_sessions.id", "survey_sessions.survey_version_id"],
            name="fk_answer_events_session_version",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["survey_version_id", "question_id"],
            [
                "surveys_questions.survey_version_id",
                "surveys_questions.question_id",
            ],
            name="fk_answer_events_version_question",
            ondelete="RESTRICT",
        ),
        Index(
            "ix_answer_events_session_question_created",
            "surveys_session_id",
            "question_id",
            "created_at",
        ),
        Index(
            "ix_answer_events_session_version",
            "surveys_session_id",
            "survey_version_id",
        ),
        Index(
            "ix_answer_events_version_question",
            "survey_version_id",
            "question_id",
        ),
        Index("ix_answer_events_question_id", "question_id"),
    )

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        sa_column_kwargs=UUID_PK_KWARGS,
    )
    surveys_session_id: uuid.UUID
    survey_version_id: uuid.UUID
    question_id: uuid.UUID
    value: Any | None = Field(default=None, sa_column=Column(JSONB, nullable=True))
