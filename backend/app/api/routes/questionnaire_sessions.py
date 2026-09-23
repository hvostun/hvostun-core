import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlmodel import col, func, select

from app.api.deps import CurrentUser, SessionDep
from app.models import (
    AnswerEvent,
    Question,
    QuestionnaireSession,
    QuestionnaireSessionPublic,
    QuestionnaireSessionsPublic,
    Recommendation,
    SessionAnswerPublic,
    SessionAnswersPublic,
    SessionRecommendation,
    SessionRecommendationItemPublic,
    SessionRecommendationItemsPublic,
)

router = APIRouter(prefix="/questionnaire-sessions", tags=["sessions"])


@router.get("/", response_model=QuestionnaireSessionsPublic)
def read_questionnaire_sessions(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 50,
    status: str | None = None,
    user_id: uuid.UUID | None = None,
    dog_id: uuid.UUID | None = None,
    questionnaire_id: uuid.UUID | None = None,
) -> Any:
    _ = current_user
    filters = []
    if status:
        filters.append(QuestionnaireSession.status == status)
    if user_id:
        filters.append(QuestionnaireSession.user_id == user_id)
    if dog_id:
        filters.append(QuestionnaireSession.dog_id == dog_id)
    if questionnaire_id:
        filters.append(QuestionnaireSession.questionnaire_id == questionnaire_id)

    count_statement = select(func.count()).select_from(QuestionnaireSession)
    statement = select(QuestionnaireSession)
    if filters:
        count_statement = count_statement.where(*filters)
        statement = statement.where(*filters)

    count = session.exec(count_statement).one()
    sessions = session.exec(
        statement.order_by(col(QuestionnaireSession.created_at).desc())
        .offset(skip)
        .limit(limit)
    ).all()
    return QuestionnaireSessionsPublic(
        data=[QuestionnaireSessionPublic.model_validate(row) for row in sessions],
        count=count,
    )


def _get_session_or_404(
    session: SessionDep, session_id: uuid.UUID
) -> QuestionnaireSession:
    row = session.get(QuestionnaireSession, session_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return row


@router.get("/{session_id}", response_model=QuestionnaireSessionPublic)
def read_questionnaire_session(
    session: SessionDep,
    current_user: CurrentUser,
    session_id: uuid.UUID,
) -> Any:
    _ = current_user
    return QuestionnaireSessionPublic.model_validate(
        _get_session_or_404(session, session_id)
    )


@router.get("/{session_id}/answers", response_model=SessionAnswersPublic)
def read_questionnaire_session_answers(
    session: SessionDep,
    current_user: CurrentUser,
    session_id: uuid.UUID,
) -> Any:
    _ = current_user
    session_row = _get_session_or_404(session, session_id)
    questions = session.exec(
        select(Question)
        .where(Question.questionnaire_id == session_row.questionnaire_id)
        .order_by(col(Question.order_number), col(Question.global_id))
    ).all()
    events = session.exec(
        select(AnswerEvent)
        .where(AnswerEvent.session_id == session_id)
        .order_by(col(AnswerEvent.created_at).desc())
    ).all()
    latest: dict[uuid.UUID, AnswerEvent] = {}
    for event in events:
        if event.question_id not in latest:
            latest[event.question_id] = event

    data = []
    for question in questions:
        event = latest.get(question.id)
        data.append(
            SessionAnswerPublic(
                question_id=question.id,
                order_number=question.order_number,
                question_text=question.text,
                value_num=event.value_num if event else None,
                value_text=event.value_text if event else None,
                value_date=event.value_date if event else None,
                answered_at=event.created_at if event else None,
            )
        )
    return SessionAnswersPublic(data=data, count=len(data))


@router.get(
    "/{session_id}/recommendations",
    response_model=SessionRecommendationItemsPublic,
)
def read_questionnaire_session_recommendations(
    session: SessionDep,
    current_user: CurrentUser,
    session_id: uuid.UUID,
) -> Any:
    _ = current_user
    _get_session_or_404(session, session_id)
    rows = session.exec(
        select(SessionRecommendation, Recommendation)
        .where(SessionRecommendation.session_id == session_id)
        .where(SessionRecommendation.recomendation_id == Recommendation.id)
        .order_by(
            col(SessionRecommendation.user_id),
            col(SessionRecommendation.chart_number),
            col(SessionRecommendation.created_at),
        )
    ).all()
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
