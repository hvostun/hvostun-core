import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlmodel import col, func, select

from app.api.deps import CurrentUser, SessionDep
from app.models import (
    Question,
    Questionnaire,
    QuestionnairePublic,
    QuestionnairesPublic,
    QuestionPublic,
    QuestionsPublic,
    Scale,
)

router = APIRouter(prefix="/questionnaires", tags=["questionnaires"])


@router.get("/", response_model=QuestionnairesPublic)
def read_questionnaires(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 50,
    name: str | None = None,
    slug: str | None = None,
) -> Any:
    _ = current_user
    filters = []
    if name:
        filters.append(col(Questionnaire.name).ilike(f"%{name}%"))
    if slug:
        filters.append(col(Questionnaire.slug).ilike(f"%{slug}%"))

    count_statement = select(func.count()).select_from(Questionnaire)
    statement = select(Questionnaire)
    if filters:
        count_statement = count_statement.where(*filters)
        statement = statement.where(*filters)

    count = session.exec(count_statement).one()
    questionnaires = session.exec(
        statement.order_by(col(Questionnaire.created_at).desc())
        .offset(skip)
        .limit(limit)
    ).all()
    return QuestionnairesPublic(
        data=[
            QuestionnairePublic.model_validate(item) for item in questionnaires
        ],
        count=count,
    )


def _get_questionnaire_or_404(
    session: SessionDep, questionnaire_id: uuid.UUID
) -> Questionnaire:
    questionnaire = session.get(Questionnaire, questionnaire_id)
    if questionnaire is None:
        raise HTTPException(status_code=404, detail="Questionnaire not found")
    return questionnaire


@router.get("/{questionnaire_id}", response_model=QuestionnairePublic)
def read_questionnaire(
    session: SessionDep,
    current_user: CurrentUser,
    questionnaire_id: uuid.UUID,
) -> Any:
    _ = current_user
    return QuestionnairePublic.model_validate(
        _get_questionnaire_or_404(session, questionnaire_id)
    )


@router.get(
    "/{questionnaire_id}/questions",
    response_model=QuestionsPublic,
)
def read_questionnaire_questions(
    session: SessionDep,
    current_user: CurrentUser,
    questionnaire_id: uuid.UUID,
) -> Any:
    _ = current_user
    _get_questionnaire_or_404(session, questionnaire_id)
    statement = (
        select(Question, Scale)
        .where(Question.questionnaire_id == questionnaire_id)
        .where(Question.scale_id == Scale.id)
        .order_by(col(Question.order_number), col(Question.global_id))
    )
    rows = session.exec(statement).all()
    return QuestionsPublic(
        data=[
            QuestionPublic(
                id=question.id,
                questionnaire_id=question.questionnaire_id,
                global_id=question.global_id,
                order_number=question.order_number,
                text=question.text,
                scale_id=question.scale_id,
                scale_name=scale.name,
                created_at=question.created_at,
                updated_at=question.updated_at,
            )
            for question, scale in rows
        ],
        count=len(rows),
    )
