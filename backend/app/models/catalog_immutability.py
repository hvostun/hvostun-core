import uuid
from datetime import date
from typing import Never

from sqlalchemy import event, inspect
from sqlalchemy.orm import Session as SASession
from sqlmodel import select

from app.models.dog import Dog, DogStatus, PlacementCode, PlacementEvent
from app.models.questionnairy import (
    AnswerEvent,
    AnswerValue,
    Question,
    Scale,
    ScaleConfig,
    ScaleType,
    SessionStatus,
    SurveyQuestion,
    SurveySession,
    SurveyVersion,
)
from app.models.recommendation import Recommendation
from app.models.user import User, UserGroup


class CatalogImmutableError(ValueError):
    pass


class JSONBValidationError(ValueError):
    pass


class DomainValueValidationError(ValueError):
    pass


def _reject_immutable(obj: object, operation: str) -> Never:
    raise CatalogImmutableError(
        f"{type(obj).__name__} is immutable and cannot be {operation}"
    )


def _new_question(session: SASession, row_id: uuid.UUID) -> Question | None:
    return next(
        (
            item
            for item in session.new
            if isinstance(item, Question) and item.id == row_id
        ),
        None,
    )


def _new_scale(session: SASession, row_id: uuid.UUID) -> Scale | None:
    return next(
        (item for item in session.new if isinstance(item, Scale) and item.id == row_id),
        None,
    )


def _validate_domain_values(session: SASession) -> None:
    for obj in session.new.union(session.dirty):
        try:
            if isinstance(obj, Dog):
                obj.status = DogStatus(obj.status)
            elif isinstance(obj, PlacementEvent):
                obj.code = PlacementCode(obj.code)
            elif isinstance(obj, SurveySession):
                obj.status = SessionStatus(obj.status)
            elif isinstance(obj, Scale):
                obj.type = ScaleType(obj.type)
            elif isinstance(obj, User):
                obj.group = UserGroup(obj.group)
        except ValueError as exc:
            raise DomainValueValidationError(str(exc)) from exc


def _validate_scale_config(scale: Scale) -> None:
    try:
        parsed = ScaleConfig.model_validate(scale.config or {})
    except ValueError as exc:
        raise JSONBValidationError(f"invalid scale config: {exc}") from exc

    if scale.type == ScaleType.INTEGER and (
        parsed.min_value is None or parsed.max_value is None
    ):
        raise JSONBValidationError(
            "integer scale config requires min_value and max_value"
        )
    scale.config = parsed.model_dump(exclude_none=True)


def _validate_answer(session: SASession, answer: AnswerEvent) -> None:
    if answer.value is None:
        return
    try:
        parsed = AnswerValue.model_validate(answer.value)
    except ValueError as exc:
        raise JSONBValidationError(f"invalid answer value: {exc}") from exc

    question = _new_question(session, answer.question_id)
    if question is None:
        question = session.get(Question, answer.question_id)
    if question is None:
        raise JSONBValidationError("answer question does not exist")

    scale = _new_scale(session, question.scale_id)
    if scale is None:
        scale = session.get(Scale, question.scale_id)
    if scale is None:
        raise JSONBValidationError("answer scale does not exist")

    scale_type = ScaleType(scale.type)
    config = ScaleConfig.model_validate(scale.config or {})
    value = parsed.value

    if value is None:
        answer.value = {"value": None}
        return
    if scale_type == ScaleType.INTEGER:
        if isinstance(value, bool) or not isinstance(value, int):
            raise JSONBValidationError("integer scale answer must be an integer")
        if config.min_value is not None and value < config.min_value:
            raise JSONBValidationError("answer is below scale min_value")
        if config.max_value is not None and value > config.max_value:
            raise JSONBValidationError("answer is above scale max_value")
        if config.legend is not None and str(value) not in config.legend:
            raise JSONBValidationError("answer has no matching legend key")
        answer.value = {"value": value}
        return
    if scale_type == ScaleType.TEXT:
        if not isinstance(value, str):
            raise JSONBValidationError("text scale answer must be a string")
        answer.value = {"value": value}
        return
    if not isinstance(value, str):
        raise JSONBValidationError("date scale answer must be an ISO date string")
    try:
        normalized = date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise JSONBValidationError("date scale answer must be an ISO date") from exc
    answer.value = {"value": normalized}


def _guard_immutable_objects(session: SASession) -> None:
    immutable_types = (SurveyVersion, Question, AnswerEvent, Recommendation)
    for obj in session.deleted:
        if isinstance(obj, (*immutable_types, Scale, SurveyQuestion)):
            _reject_immutable(obj, "deleted")
    for obj in session.dirty:
        if isinstance(obj, immutable_types) and session.is_modified(
            obj, include_collections=False
        ):
            _reject_immutable(obj, "updated")
        if isinstance(obj, SurveyQuestion) and session.is_modified(
            obj, include_collections=False
        ):
            _reject_immutable(obj, "updated")
        if isinstance(obj, SurveySession):
            state = inspect(obj)
            if state is None:
                continue
            history = state.attrs.survey_version_id.history
            if history.has_changes():
                _reject_immutable(obj, "moved to another survey version")


def _guard_new_version_links(session: SASession) -> None:
    new_session_version_ids = {
        item.survey_version_id
        for item in session.new
        if isinstance(item, SurveySession)
    }
    for version_id in sorted(new_session_version_ids, key=str):
        session.get(SurveyVersion, version_id, with_for_update=True)

    for obj in session.new:
        if not isinstance(obj, SurveyQuestion):
            continue
        session.get(SurveyVersion, obj.survey_version_id, with_for_update=True)
        has_session = session.execute(
            select(SurveySession.id)
            .where(SurveySession.survey_version_id == obj.survey_version_id)
            .limit(1)
        ).scalar_one_or_none()
        if has_session is not None:
            raise CatalogImmutableError(
                "questions cannot be added after the survey version's first session"
            )


@event.listens_for(SASession, "before_flush")
def validate_catalog(
    session: SASession, _flush_context: object, _instances: object
) -> None:
    _validate_domain_values(session)
    _guard_immutable_objects(session)
    _guard_new_version_links(session)

    for obj in session.new:
        if isinstance(obj, Scale):
            _validate_scale_config(obj)
        elif isinstance(obj, AnswerEvent):
            _validate_answer(session, obj)
    for obj in session.dirty:
        if isinstance(obj, Scale) and session.is_modified(
            obj, include_collections=False
        ):
            _validate_scale_config(obj)
