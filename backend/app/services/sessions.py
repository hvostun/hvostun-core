import json
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import Text, case, cast, literal_column
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, func, select

from app.models import (
    AnswerEvent,
    Dog,
    Owner,
    Question,
    Recommendation,
    Scale,
    SessionRecommendation,
    Survey,
    SurveyQuestion,
    SurveyQuestionGroup,
    SurveySession,
    SurveyVersion,
    User,
    UserGroup,
)
from app.services import dictionaries as dictionary_service

MANUAL_CHART_NUMBER = 0
MANUAL_WEIGHT = 1.0
WEIGHT_MIN = 0.0
WEIGHT_MAX = 1.0
UNANSWERED_FILTER = "unanswered"
MISSING_ANSWER = -999
DEFAULT_SCALE_MIN = 0
DEFAULT_SCALE_MAX = 4

_LEGEND_LINE = re.compile(r"^(-?\d+)\s*(?:[-–]\s+)?(.*)$")


class SessionNotFoundError(LookupError):
    pass


class SessionRecommendationError(ValueError):
    pass


class SessionRecommendationPermissionError(PermissionError):
    pass


def can_manage_all_session_recommendations(user: User) -> bool:
    return user.is_superuser or user.group == UserGroup.ADMIN


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


def dog_session_facts(
    session: Session, dog: Dog, session_row: SurveySession
) -> dict[str, Any]:
    at = session_calendar_date(session_row.created_at)
    return {
        "id": dog.id,
        "name": dog.name,
        "sex": dictionary_service.label_for(
            session, dictionary_service.DOGS_SEX_KEY, dog.sex
        ),
        "age": format_dog_age(dog.birthday, at),
        "breed": dog.breed or "",
        "mixed": dog.mixed,
        "neutered": dog.neutered,
        "status": dictionary_service.label_for(
            session, dictionary_service.DOGS_STATUS_KEY, dog.status
        ),
        "days_since_status": days_since_status(
            dog.status_at, session_row.created_at
        ),
        "weight": dog.weight,
        "height": dog.height,
        "history": dog.history,
    }


@dataclass(frozen=True)
class SessionContext:
    row: SurveySession
    owner: Owner
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
    progress: dict[str, Any]


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


def _scale_bounds(config: object) -> tuple[float, float]:
    min_value = float(DEFAULT_SCALE_MIN)
    max_value = float(DEFAULT_SCALE_MAX)
    if isinstance(config, dict):
        if config.get("min_value") is not None:
            min_value = float(config["min_value"])
        if config.get("max_value") is not None:
            max_value = float(config["max_value"])
    return min_value, max_value


def answer_progress(
    session: Session, value: object, config: object, category: object
) -> dict[str, Any]:
    color = dictionary_service.group_color(session, str(category))
    hidden = {"show_bar": False, "percent": 0, "color": color}
    scalar = answer_scalar(value)
    if scalar is None or scalar == "":
        return hidden
    try:
        number = float(scalar)
    except (TypeError, ValueError):
        return hidden
    if number == MISSING_ANSWER:
        return hidden
    if number == 0:
        return {"show_bar": True, "percent": 0, "color": color}
    min_value, max_value = _scale_bounds(config)
    span = max_value - min_value - 1
    if span <= 0:
        percent = 0
    else:
        percent = (number - min_value - 1) / span * 100
    percent = max(0, min(100, round(percent)))
    return {"show_bar": True, "percent": percent, "color": color}


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
            SurveySession, Owner, Dog, SurveyVersion, Survey
        )
        .where(SurveySession.id == session_id)
        .where(SurveySession.owner_id == Owner.id)
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
        .order_by(col(SurveyQuestion.display_num), col(Question.id))
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
                progress=answer_progress(session, value, scale.config, link.group),
            )
        )
    return answers


def group_label(session: Session, code: str | None) -> str:
    text = "" if code is None else str(code)
    if not text:
        return ""
    return dictionary_service.group_name(session, text)


def session_answer_categories(
    session: Session, groups: list[str] | None = None
) -> list[dict[str, str]]:
    codes = [item.value for item in SurveyQuestionGroup]
    for code in groups or []:
        if code and code not in codes:
            codes.append(code)
    return [{"value": code, "label": group_label(session, code)} for code in codes]


def session_answer_values(answers: list[SessionAnswer]) -> list[str]:
    values = {item.display_value for item in answers if item.display_value}
    return sorted(values, key=lambda value: (len(value), value))


def filter_session_answers(
    answers: list[SessionAnswer],
    *,
    category: str = "",
    answer: str = "",
) -> list[SessionAnswer]:
    filtered = answers
    if category:
        filtered = [item for item in filtered if str(item.link.group) == category]
    if answer == UNANSWERED_FILTER:
        filtered = [item for item in filtered if not item.display_value]
    elif answer:
        filtered = [item for item in filtered if item.display_value == answer]
    return filtered


def get_session_recommendations(
    session: Session, session_id: uuid.UUID, current_user: User
) -> list[tuple[SessionRecommendation, Recommendation, User]]:
    statement = (
        select(SessionRecommendation, Recommendation, User)
        .where(SessionRecommendation.session_id == session_id)
        .where(SessionRecommendation.recomendation_id == Recommendation.id)
        .where(SessionRecommendation.user_id == User.id)
    )
    if not can_manage_all_session_recommendations(current_user):
        statement = statement.where(SessionRecommendation.user_id == current_user.id)
    return list(
        session.exec(
            statement.order_by(
                col(SessionRecommendation.user_id),
                col(SessionRecommendation.chart_number),
                col(SessionRecommendation.created_at),
            )
        ).all()
    )


def session_recommendation_counts(
    session: Session, session_ids: list[uuid.UUID], current_user: User
) -> dict[uuid.UUID, tuple[int, int]]:
    counts = dict.fromkeys(session_ids, (0, 0))
    if not session_ids:
        return counts
    statement = (
        select(
            SessionRecommendation.session_id,
            func.count(),
            func.count(func.distinct(SessionRecommendation.user_id)),
        )
        .where(col(SessionRecommendation.session_id).in_(session_ids))
    )
    if not can_manage_all_session_recommendations(current_user):
        statement = statement.where(SessionRecommendation.user_id == current_user.id)
    rows = session.exec(statement.group_by(SessionRecommendation.session_id)).all()
    for session_id, rec_count, user_count in rows:
        counts[session_id] = (int(rec_count), int(user_count))
    return counts


def answer_rates(
    session: Session, session_ids: list[uuid.UUID]
) -> dict[uuid.UUID, int | None]:
    """Share of latest answers that are not the missing-answer marker.

    Computed only for the given sessions (one list page). Sorting the
    session list by this percent is deferred: it would aggregate
    answer_events before LIMIT.
    """
    rates: dict[uuid.UUID, int | None] = dict.fromkeys(session_ids)
    if not session_ids:
        return rates
    latest = (
        select(
            AnswerEvent.surveys_session_id,
            AnswerEvent.question_id,
            AnswerEvent.value,
        )
        .where(col(AnswerEvent.surveys_session_id).in_(session_ids))
        .distinct(
            col(AnswerEvent.surveys_session_id),
            col(AnswerEvent.question_id),
        )
        .order_by(
            col(AnswerEvent.surveys_session_id),
            col(AnswerEvent.question_id),
            col(AnswerEvent.created_at).desc(),
            col(AnswerEvent.id).desc(),
        )
        .subquery()
    )
    value_json = cast(latest.c.value, JSONB)
    value_type = func.jsonb_typeof(value_json)
    # Stored answers are a bare JSON number. Wrapped {"value": ...} is also accepted.
    scalar_text = case(
        (value_type == "number", cast(value_json, Text)),
        (value_type == "string", value_json.op("#>>")(literal_column("'{}'::text[]"))),
        (value_type == "object", value_json["value"].astext),
    )
    answered = (
        select(
            latest.c.surveys_session_id.label("session_id"),
            func.count().label("answered"),
        )
        .where(scalar_text.is_not(None))
        .where(scalar_text != str(MISSING_ANSWER))
        .group_by(latest.c.surveys_session_id)
        .subquery()
    )
    totals = (
        select(
            SurveyQuestion.survey_version_id,
            func.count().label("total"),
        )
        .where(
            col(SurveyQuestion.survey_version_id).in_(
                select(SurveySession.survey_version_id).where(
                    col(SurveySession.id).in_(session_ids)
                )
            )
        )
        .group_by(col(SurveyQuestion.survey_version_id))
        .subquery()
    )
    rows = session.exec(
        select(
            SurveySession.id,
            totals.c.total,
            func.coalesce(answered.c.answered, 0),
        )
        .where(col(SurveySession.id).in_(session_ids))
        .outerjoin(
            totals,
            col(SurveySession.survey_version_id) == totals.c.survey_version_id,
        )
        .outerjoin(answered, col(SurveySession.id) == answered.c.session_id)
    ).all()
    for session_id, total, answered_count in rows:
        if total is None or int(total) == 0:
            rates[session_id] = None
            continue
        rates[session_id] = round(int(answered_count) * 100 / int(total))
    return rates


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


def _apply_session_recommendation_update(
    session: Session,
    *,
    session_id: uuid.UUID,
    recommendation_id: uuid.UUID,
    current_user: User,
    chart_number: int,
    weight: float,
    comment: str | None,
) -> SessionRecommendation:
    row = get_session_recommendation(session, session_id, recommendation_id)
    if (
        not can_manage_all_session_recommendations(current_user)
        and row.user_id != current_user.id
    ):
        raise SessionRecommendationPermissionError(
            "Можно изменять только свои рекомендации"
        )
    if chart_number < 0:
        raise SessionRecommendationError("Очередность не может быть отрицательной")
    if weight < WEIGHT_MIN or weight > WEIGHT_MAX:
        raise SessionRecommendationError("Критичность должна быть от 0 до 1")
    text = comment.strip() if comment else None
    row.chart_number = chart_number
    row.weight = weight
    row.comment = text or None
    session.add(row)
    return row


def update_session_recommendations(
    session: Session,
    *,
    session_id: uuid.UUID,
    current_user: User,
    updates: list[tuple[uuid.UUID, int, float, str | None]],
) -> list[SessionRecommendation]:
    get_accessible_session(session, session_id, current_user)
    try:
        rows = [
            _apply_session_recommendation_update(
                session,
                session_id=session_id,
                recommendation_id=recommendation_id,
                current_user=current_user,
                chart_number=chart_number,
                weight=weight,
                comment=comment,
            )
            for recommendation_id, chart_number, weight, comment in updates
        ]
        session.commit()
    except Exception:
        session.rollback()
        raise
    for row in rows:
        session.refresh(row)
    return rows


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
    return update_session_recommendations(
        session,
        session_id=session_id,
        current_user=current_user,
        updates=[(recommendation_id, chart_number, weight, comment)],
    )[0]


def delete_session_recommendation(
    session: Session,
    *,
    session_id: uuid.UUID,
    current_user: User,
    recommendation_id: uuid.UUID,
) -> None:
    get_accessible_session(session, session_id, current_user)
    row = get_session_recommendation(session, session_id, recommendation_id)
    if (
        not can_manage_all_session_recommendations(current_user)
        and row.user_id != current_user.id
    ):
        raise SessionRecommendationPermissionError(
            "Можно удалить только свою рекомендацию"
        )
    session.delete(row)
    session.commit()


def group_recommendations(
    rows: list[tuple[SessionRecommendation, Recommendation, User]],
) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    for item, catalog, author in rows:
        entry = {
            "id": item.id,
            "recommendation_name": catalog.name,
            "recommendation_slug": catalog.slug,
            "recommendation_text": catalog.text,
            "author_name": author.full_name or author.email,
            "user_id": item.user_id,
            "chart_number": item.chart_number,
            "weight": item.weight,
            "comment": item.comment,
        }
        if groups and groups[-1]["user_id"] == item.user_id:
            groups[-1]["recommendations"].append(entry)
        else:
            groups.append({"user_id": item.user_id, "recommendations": [entry]})
    return groups
