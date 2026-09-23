import uuid
from typing import Any

from fastapi import APIRouter
from sqlmodel import col, func, select

from app.api.deps import CurrentUser, SessionDep
from app.models import (
    QuestionnaireSession,
    QuestionnaireSessionPublic,
    QuestionnaireSessionsPublic,
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
