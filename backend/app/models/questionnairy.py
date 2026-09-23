import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from sqlalchemy import Column, Numeric, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.models.base import CreatedAtMixin, TimestampMixin


class SessionStatus(StrEnum):
    DRAFT = "draft"
    FINISHED = "finished"
    CANCELED = "canceled"


class ScaleType(StrEnum):
    INTEGER = "integer"
    TEXT = "text"
    DATE = "date"


class Questionnaire(TimestampMixin, SQLModel, table=True):
    __tablename__ = "questionnaires"  # type: ignore[assignment]  # pyright: ignore[reportAssignmentType]

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(sa_type=Text)
    slug: str = Field(unique=True, index=True, sa_type=Text)
    description: str | None = Field(default=None, sa_type=Text)


class QuestionnairePublic(SQLModel):
    id: uuid.UUID
    name: str
    slug: str
    description: str | None = None
    created_at: datetime
    updated_at: datetime


class QuestionnairesPublic(SQLModel):
    data: list[QuestionnairePublic]
    count: int


class Scale(TimestampMixin, SQLModel, table=True):
    __tablename__ = "scales"  # type: ignore[assignment]  # pyright: ignore[reportAssignmentType]

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(sa_type=Text)
    description: str | None = Field(default=None, sa_type=Text)
    type: str = Field(sa_type=Text)
    min_value: int | None = None
    max_value: int | None = None


class Question(TimestampMixin, SQLModel, table=True):
    __tablename__ = "questions"  # type: ignore[assignment]  # pyright: ignore[reportAssignmentType]

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    questionnaire_id: uuid.UUID = Field(foreign_key="questionnaires.id")
    global_id: uuid.UUID = Field(default_factory=uuid.uuid4, unique=True, index=True)
    order_number: int
    text: str = Field(sa_type=Text)
    scale_id: uuid.UUID = Field(foreign_key="scales.id")


class QuestionPublic(SQLModel):
    id: uuid.UUID
    questionnaire_id: uuid.UUID
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


class QuestionnaireSession(TimestampMixin, SQLModel, table=True):
    __tablename__ = "questionnaire_sessions"  # type: ignore[assignment]  # pyright: ignore[reportAssignmentType]

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id")
    dog_id: uuid.UUID = Field(foreign_key="dogs.id")
    questionnaire_id: uuid.UUID = Field(foreign_key="questionnaires.id")
    status: str = Field(default=SessionStatus.DRAFT, sa_type=Text)
    client_metadata: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(JSONB, nullable=True),
    )


class QuestionnaireSessionPublic(SQLModel):
    id: uuid.UUID
    user_id: uuid.UUID
    dog_id: uuid.UUID
    questionnaire_id: uuid.UUID
    status: str
    client_metadata: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class QuestionnaireSessionsPublic(SQLModel):
    data: list[QuestionnaireSessionPublic]
    count: int


class SessionAnswerPublic(SQLModel):
    question_id: uuid.UUID
    order_number: int
    question_text: str
    value_num: Decimal | None = None
    value_text: str | None = None
    value_date: date | None = None
    answered_at: datetime | None = None


class SessionAnswersPublic(SQLModel):
    data: list[SessionAnswerPublic]
    count: int


class AnswerEvent(CreatedAtMixin, SQLModel, table=True):
    __tablename__ = "answer_events"  # type: ignore[assignment]  # pyright: ignore[reportAssignmentType]

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    session_id: uuid.UUID = Field(
        foreign_key="questionnaire_sessions.id", ondelete="CASCADE"
    )
    question_id: uuid.UUID = Field(foreign_key="questions.id")
    value_num: Decimal | None = Field(
        default=None, sa_column=Column(Numeric, nullable=True)
    )
    value_text: str | None = Field(default=None, sa_type=Text)
    value_date: date | None = None
