import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlmodel import col, func, select

from app.api.deps import CurrentUser, SessionDep
from app.models import (
    QuestionPublic,
    QuestionsPublic,
    Survey,
    SurveyPublic,
    SurveysPublic,
    SurveyVersionPublic,
    SurveyVersionsPublic,
)
from app.pagination import execute_page, normalize_offset_limit
from app.services import catalog

router = APIRouter(prefix="/surveys", tags=["surveys"])


@router.get("/", response_model=SurveysPublic)
def read_surveys(
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
        filters.append(col(Survey.name).ilike(f"%{name}%"))
    if slug:
        filters.append(col(Survey.slug).ilike(f"%{slug}%"))

    count_statement = select(func.count()).select_from(Survey)
    statement = select(Survey)
    if filters:
        count_statement = count_statement.where(*filters)
        statement = statement.where(*filters)

    skip, limit = normalize_offset_limit(skip, limit)
    surveys, count = execute_page(
        session,
        count_statement,
        statement.order_by(col(Survey.created_at).desc()),
        offset=skip,
        limit=limit,
    )
    return SurveysPublic(
        data=[SurveyPublic.model_validate(item) for item in surveys],
        count=count,
    )


def _get_survey_or_404(session: SessionDep, survey_id: uuid.UUID) -> Survey:
    try:
        return catalog.get_survey(session, survey_id)
    except catalog.CatalogNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Survey not found") from exc


@router.get("/{survey_id}", response_model=SurveyPublic)
def read_survey(
    session: SessionDep,
    current_user: CurrentUser,
    survey_id: uuid.UUID,
) -> Any:
    _ = current_user
    return SurveyPublic.model_validate(_get_survey_or_404(session, survey_id))


@router.get("/{survey_id}/versions", response_model=SurveyVersionsPublic)
def read_survey_versions(
    session: SessionDep,
    current_user: CurrentUser,
    survey_id: uuid.UUID,
) -> Any:
    _ = current_user
    try:
        versions = catalog.list_survey_versions(session, survey_id)
    except catalog.CatalogNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return SurveyVersionsPublic(
        data=[SurveyVersionPublic.model_validate(row) for row in versions],
        count=len(versions),
    )


@router.get(
    "/versions/{survey_version_id}/questions",
    response_model=QuestionsPublic,
)
def read_survey_version_questions(
    session: SessionDep,
    current_user: CurrentUser,
    survey_version_id: uuid.UUID,
) -> Any:
    _ = current_user
    try:
        rows = catalog.get_version_questions(session, survey_version_id)
    except catalog.CatalogNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return QuestionsPublic(
        data=[
            QuestionPublic(
                id=question.id,
                survey_version_id=link.survey_version_id,
                global_id=question.global_id,
                order_number=link.order_num,
                text=question.text,
                scale_id=question.scale_id,
                scale_name=scale.name,
                created_at=question.created_at,
                updated_at=question.updated_at,
            )
            for question, scale, link in rows
        ],
        count=len(rows),
    )
