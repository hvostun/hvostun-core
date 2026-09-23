import uuid
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Any

from sqlalchemy import Column, Numeric
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
    __tablename__ = "questionnaires"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str
    slug: str = Field(unique=True, index=True)
    description: str | None = None


class Scale(TimestampMixin, SQLModel, table=True):
    __tablename__ = "scales"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    type: str
    min_value: int | None = None
    max_value: int | None = None


class Question(TimestampMixin, SQLModel, table=True):
    __tablename__ = "questions"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    questionnaire_id: uuid.UUID = Field(foreign_key="questionnaires.id")
    global_number: int
    order_number: int
    text: str
    scale_id: uuid.UUID = Field(foreign_key="scales.id")


class QuestionnaireSession(TimestampMixin, SQLModel, table=True):
    __tablename__ = "questionnaire_sessions"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id")
    dog_id: uuid.UUID = Field(foreign_key="dogs.id")
    questionnaire_id: uuid.UUID = Field(foreign_key="questionnaires.id")
    status: str = Field(default=SessionStatus.DRAFT)
    client_metadata: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(JSONB, nullable=True),
    )


class AnswerEvent(CreatedAtMixin, SQLModel, table=True):
    __tablename__ = "answer_events"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    session_id: uuid.UUID = Field(
        foreign_key="questionnaire_sessions.id", ondelete="CASCADE"
    )
    question_id: uuid.UUID = Field(foreign_key="questions.id")
    value_num: Decimal | None = Field(
        default=None, sa_column=Column(Numeric, nullable=True)
    )
    value_text: str | None = None
    value_date: date | None = None
