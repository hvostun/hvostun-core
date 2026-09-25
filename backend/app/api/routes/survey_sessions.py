import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlmodel import col, func, select

from app.api.deps import CurrentUser, SessionDep
from app.models import (
    SessionAnswerPublic,
    SessionAnswersPublic,
    SessionRecommendationItemPublic,
    SessionRecommendationItemsPublic,
    SurveySession,
    SurveySessionPublic,
    SurveySessionsPublic,
)
from app.pagination import execute_page, normalize_offset_limit
from app.services import sessions as session_service

router = APIRouter(prefix="/survey-sessions", tags=["sessions"])


@router.get("/", response_model=SurveySessionsPublic)
def read_survey_sessions(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 50,
    status: str | None = None,
    owner_id: uuid.UUID | None = None,
    dog_id: uuid.UUID | None = None,
    survey_version_id: uuid.UUID | None = None,
) -> Any:
    _ = current_user
    filters = []
    if status:
        filters.append(SurveySession.status == status)
    if owner_id:
        filters.append(SurveySession.owner_id == owner_id)
    if dog_id:
        filters.append(SurveySession.dog_id == dog_id)
    if survey_version_id:
        filters.append(SurveySession.survey_version_id == survey_version_id)

    count_statement = select(func.count()).select_from(SurveySession)
    statement = select(SurveySession)
    if filters:
        count_statement = count_statement.where(*filters)
        statement = statement.where(*filters)

    skip, limit = normalize_offset_limit(skip, limit)
    sessions, count = execute_page(
        session,
        count_statement,
        statement.order_by(col(SurveySession.created_at).desc()),
        offset=skip,
        limit=limit,
    )
    return SurveySessionsPublic(
        data=[SurveySessionPublic.model_validate(row) for row in sessions],
        count=count,
    )


def _get_session_or_404(session: SessionDep, session_id: uuid.UUID) -> SurveySession:
    try:
        return session_service.get_session(session, session_id)
    except session_service.SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc


@router.get("/{session_id}", response_model=SurveySessionPublic)
def read_survey_session(
    session: SessionDep,
    current_user: CurrentUser,
    session_id: uuid.UUID,
) -> Any:
    _ = current_user
    row = _get_session_or_404(session, session_id)
    return SurveySessionPublic.model_validate(row)


@router.get("/{session_id}/answers", response_model=SessionAnswersPublic)
def read_survey_session_answers(
    session: SessionDep,
    current_user: CurrentUser,
    session_id: uuid.UUID,
) -> Any:
    _ = current_user
    session_row = _get_session_or_404(session, session_id)
    answers = session_service.get_session_answers(session, session_row)
    data = [
        SessionAnswerPublic(
            question_id=item.question.id,
            order_number=item.link.order_num,
            question_text=item.question.text,
            value=item.event.value if item.event else None,
            answered_at=item.event.created_at if item.event else None,
        )
        for item in answers
    ]
    return SessionAnswersPublic(data=data, count=len(data))


@router.get(
    "/{session_id}/recommendations",
    response_model=SessionRecommendationItemsPublic,
)
def read_survey_session_recommendations(
    session: SessionDep,
    current_user: CurrentUser,
    session_id: uuid.UUID,
) -> Any:
    _ = current_user
    _get_session_or_404(session, session_id)
    rows = session_service.get_session_recommendations(session, session_id)
    data = [
        SessionRecommendationItemPublic(
            id=item.id,
            user_id=item.user_id,
            session_id=item.session_id,
            recomendation_id=item.recomendation_id,
            chart_number=item.chart_number,
            weight=item.weight,
            comment=item.comment,
            created_at=item.created_at,
            updated_at=item.updated_at,
            recommendation_name=catalog.name,
            recommendation_slug=catalog.slug,
            recommendation_text=catalog.text,
        )
        for item, catalog in rows
    ]
    return SessionRecommendationItemsPublic(data=data, count=len(data))
