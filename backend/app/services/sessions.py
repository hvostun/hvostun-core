import json
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select

from app.models import (
    AnswerEvent,
    Dog,
    Question,
    Recommendation,
    Scale,
    SessionRecommendation,
    Survey,
    SurveyQuestion,
    SurveySession,
    SurveyVersion,
    User,
)

MANUAL_CHART_NUMBER = 0
MANUAL_WEIGHT = 1.0
WEIGHT_MIN = 0.0
WEIGHT_MAX = 1.0

_LEGEND_LINE = re.compile(r"^(-?\d+)\s*(?:[-–]\s+)?(.*)$")


class SessionNotFoundError(LookupError):
    pass


class SessionRecommendationError(ValueError):
    pass


def parse_chart_number(raw: str) -> int:
    text = raw.strip()
    if not text:
        return MANUAL_CHART_NUMBER
    try:
        value = int(text)
    except ValueError as exc:
        raise SessionRecommendationError(
            "Очередность должна быть целым числом"
        ) from exc
    if value < 0:
        raise SessionRecommendationError("Очередность не может быть отрицательной")
    return value


def parse_weight(raw: str) -> float:
    text = raw.strip()
    if not text:
        return MANUAL_WEIGHT
    try:
        value = float(text)
    except ValueError as exc:
        raise SessionRecommendationError("Критичность должна быть числом") from exc
    if value < WEIGHT_MIN or value > WEIGHT_MAX:
        raise SessionRecommendationError("Критичность должна быть от 0 до 1")
    return value


def session_calendar_date(created_at: datetime | None) -> date | None:
    if created_at is None:
        return None
    if created_at.tzinfo is not None:
        return created_at.astimezone(UTC).date()
    return created_at.date()


def days_since_status(
    status_at: date | None, created_at: datetime | None
) -> int | None:
    session_day = session_calendar_date(created_at)
    if status_at is None or session_day is None:
        return None
    return (session_day - status_at).days


def format_dog_age(birthday: date | None, at: date | None) -> str:
    if birthday is None or at is None or birthday > at:
        return ""
    years = at.year - birthday.year
    months = at.month - birthday.month
    if at.day < birthday.day:
        months -= 1
    if months < 0:
        years -= 1
        months += 12
    parts: list[str] = []
    if years:
        parts.append(f"{years} г.")
    if months or not parts:
        parts.append(f"{months} мес.")
    return " ".join(parts)


def dog_session_facts(dog: Dog, session_row: SurveySession) -> dict[str, Any]:
    at = session_calendar_date(session_row.created_at)
    return {
        "id": dog.id,
        "name": dog.name,
        "sex": dog.sex or "",
        "age": format_dog_age(dog.birthday, at),
        "breed": dog.breed or "",
        "mixed": dog.mixed,
        "neutered": dog.neutered,
        "status": dog.status,
        "days_since_status": days_since_status(
            dog.status_at, session_row.created_at
        ),
    }


@dataclass(frozen=True)
class SessionContext:
    row: SurveySession
    owner: User
    dog: Dog
    version: SurveyVersion
    survey: Survey


@dataclass(frozen=True)
class SessionAnswer:
    question: Question
    link: SurveyQuestion
    event: AnswerEvent | None
    display_value: str
    legend: str


def answer_scalar(value: object) -> object:
    if isinstance(value, dict) and "value" in value:
        return value["value"]
    return value


def format_answer(value: object) -> str:
    scalar = answer_scalar(value)
    if scalar is None:
        return ""
    if isinstance(scalar, str):
        return scalar
    return json.dumps(scalar, ensure_ascii=False)


def legend_map(config: object) -> dict[str, str]:
    if not isinstance(config, dict):
        return {}
    legend = config.get("legend")
    if isinstance(legend, dict):
        return {str(key): str(label) for key, label in legend.items()}
    if not isinstance(legend, str):
        return {}
    parsed: dict[str, str] = {}
    for line in legend.splitlines():
        match = _LEGEND_LINE.match(line.strip())
        if match:
            parsed[match.group(1)] = match.group(2).strip()
    return parsed


def legend_label(config: object, value: object) -> str:
    scalar = answer_scalar(value)
    if scalar is None:
        return ""
    return legend_map(config).get(str(scalar), "")


def get_session(session: Session, session_id: uuid.UUID) -> SurveySession:
    row = session.get(SurveySession, session_id)
    if row is None:
        raise SessionNotFoundError("Session not found")
    return row


def get_accessible_session(
    session: Session, session_id: uuid.UUID, current_user: User
) -> SurveySession:
    # Any active authenticated user can read every session and its answers.
    _ = current_user
    return get_session(session, session_id)


def answer_event_filters(
    *,
    surveys_session_id: uuid.UUID | None = None,
    survey_version_id: uuid.UUID | None = None,
    question_id: uuid.UUID | None = None,
) -> list[Any]:
    filters: list[Any] = []
    if surveys_session_id:
        filters.append(AnswerEvent.surveys_session_id == surveys_session_id)
    if survey_version_id:
        filters.append(AnswerEvent.survey_version_id == survey_version_id)
    if question_id:
        filters.append(AnswerEvent.question_id == question_id)
    return filters


def get_session_context(
    session: Session, session_id: uuid.UUID, current_user: User
) -> SessionContext:
    get_accessible_session(session, session_id, current_user)
    result = session.exec(
        select(  # type: ignore[call-overload]
            SurveySession, User, Dog, SurveyVersion, Survey
        )
        .where(SurveySession.id == session_id)
        .where(SurveySession.owner_id == User.id)
        .where(SurveySession.dog_id == Dog.id)
        .where(SurveySession.survey_version_id == SurveyVersion.id)
        .where(SurveyVersion.survey_id == Survey.id)
    ).first()
    if result is None:
        raise SessionNotFoundError("Session context not found")
    row, owner, dog, version, survey = result
    return SessionContext(row, owner, dog, version, survey)


def get_session_answers(
    session: Session, session_row: SurveySession
) -> list[SessionAnswer]:
    question_rows = session.exec(
        select(Question, SurveyQuestion, Scale)
        .where(SurveyQuestion.survey_version_id == session_row.survey_version_id)
        .where(SurveyQuestion.question_id == Question.id)
        .where(Question.scale_id == Scale.id)
        .order_by(col(SurveyQuestion.order_num), col(Question.id))
    ).all()
    events = session.exec(
        select(AnswerEvent)
        .where(AnswerEvent.surveys_session_id == session_row.id)
        .order_by(
            col(AnswerEvent.created_at).desc(),
            col(AnswerEvent.id).desc(),
        )
    ).all()
    latest: dict[uuid.UUID, AnswerEvent] = {}
    for event in events:
        latest.setdefault(event.question_id, event)

    answers: list[SessionAnswer] = []
    for question, link, scale in question_rows:
        latest_event = latest.get(question.id)
        value = latest_event.value if latest_event else None
        answers.append(
            SessionAnswer(
                question=question,
                link=link,
                event=latest_event,
                display_value=format_answer(value),
                legend=legend_label(scale.config, value),
            )
        )
    return answers


def get_session_recommendations(
    session: Session, session_id: uuid.UUID
) -> list[tuple[SessionRecommendation, Recommendation]]:
    return list(
        session.exec(
            select(SessionRecommendation, Recommendation)
            .where(SessionRecommendation.session_id == session_id)
            .where(SessionRecommendation.recomendation_id == Recommendation.id)
            .order_by(
                col(SessionRecommendation.user_id),
                col(SessionRecommendation.chart_number),
                col(SessionRecommendation.created_at),
            )
        ).all()
    )


def list_catalog_recommendations(session: Session) -> list[Recommendation]:
    return list(
        session.exec(
            select(Recommendation).order_by(
                col(Recommendation.name),
                col(Recommendation.slug),
            )
        ).all()
    )


def available_recommendations_for_user(
    session: Session,
    *,
    session_id: uuid.UUID,
    user_id: uuid.UUID,
) -> list[Recommendation]:
    assigned_ids = set(
        session.exec(
            select(SessionRecommendation.recomendation_id)
            .where(SessionRecommendation.session_id == session_id)
            .where(SessionRecommendation.user_id == user_id)
        ).all()
    )
    return [
        row
        for row in list_catalog_recommendations(session)
        if row.id not in assigned_ids
    ]


def add_session_recommendation(
    session: Session,
    *,
    session_id: uuid.UUID,
    current_user: User,
    recomendation_id: uuid.UUID,
    comment: str | None = None,
    chart_number: int = MANUAL_CHART_NUMBER,
    weight: float = MANUAL_WEIGHT,
) -> SessionRecommendation:
    get_accessible_session(session, session_id, current_user)
    catalog = session.get(Recommendation, recomendation_id)
    if catalog is None:
        raise SessionRecommendationError("Рекомендация не найдена")
    if chart_number < 0:
        raise SessionRecommendationError("Очередность не может быть отрицательной")
    if weight < WEIGHT_MIN or weight > WEIGHT_MAX:
        raise SessionRecommendationError("Критичность должна быть от 0 до 1")
    text = comment.strip() if comment else None
    row = SessionRecommendation(
        user_id=current_user.id,
        session_id=session_id,
        recomendation_id=recomendation_id,
        chart_number=chart_number,
        weight=weight,
        comment=text or None,
    )
    session.add(row)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise SessionRecommendationError("Эта рекомендация уже добавлена") from exc
    session.refresh(row)
    return row


def get_session_recommendation(
    session: Session, session_id: uuid.UUID, recommendation_id: uuid.UUID
) -> SessionRecommendation:
    row = session.get(SessionRecommendation, recommendation_id)
    if row is None or row.session_id != session_id:
        raise SessionNotFoundError("Session recommendation not found")
    return row


def update_session_recommendation(
    session: Session,
    *,
    session_id: uuid.UUID,
    current_user: User,
    recommendation_id: uuid.UUID,
    chart_number: int,
    weight: float,
    comment: str | None = None,
) -> SessionRecommendation:
    get_accessible_session(session, session_id, current_user)
    row = get_session_recommendation(session, session_id, recommendation_id)
    if chart_number < 0:
        raise SessionRecommendationError("Очередность не может быть отрицательной")
    if weight < WEIGHT_MIN or weight > WEIGHT_MAX:
        raise SessionRecommendationError("Критичность должна быть от 0 до 1")
    text = comment.strip() if comment else None
    row.chart_number = chart_number
    row.weight = weight
    row.comment = text or None
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def group_recommendations(
    rows: list[tuple[SessionRecommendation, Recommendation]],
) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    for item, catalog in rows:
        entry = {
            "id": item.id,
            "recommendation_name": catalog.name,
            "recommendation_slug": catalog.slug,
            "recommendation_text": catalog.text,
            "chart_number": item.chart_number,
            "weight": item.weight,
            "comment": item.comment,
        }
        if groups and groups[-1]["user_id"] == item.user_id:
            groups[-1]["recommendations"].append(entry)
        else:
            groups.append({"user_id": item.user_id, "recommendations": [entry]})
    return groups
