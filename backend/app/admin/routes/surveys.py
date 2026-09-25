import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from sqlmodel import col, func, select

from app.admin.deps import CurrentUser, SessionDep
from app.admin.templating import PAGE_SIZE, cell, list_context, templates
from app.models import Survey, SurveyVersion
from app.pagination import execute_page, page_window
from app.services import catalog

router = APIRouter()


@router.get("/surveys")
def surveys_page(
    request: Request,
    session: SessionDep,
    user: CurrentUser,
    page: int = 1,
    name: str = "",
    slug: str = "",
) -> Any:
    offset, limit, page = page_window(page, PAGE_SIZE)
    filters: list[Any] = []
    if name:
        filters.append(col(Survey.name).ilike(f"%{name}%"))
    if slug:
        filters.append(col(Survey.slug).ilike(f"%{slug}%"))
    count_stmt = select(func.count()).select_from(Survey)
    stmt = (
        select(Survey, func.max(SurveyVersion.version_num))
        .outerjoin(SurveyVersion, col(SurveyVersion.survey_id) == Survey.id)
        .group_by(col(Survey.id))
    )
    if filters:
        count_stmt = count_stmt.where(*filters)
        stmt = stmt.where(*filters)
    rows, count = execute_page(
        session,
        count_stmt,
        stmt.order_by(col(Survey.created_at).desc()),
        offset=offset,
        limit=limit,
    )
    return templates.TemplateResponse(
        request,
        "list.html",
        list_context(
            request=request,
            user=user,
            title="Анкеты",
            columns=[
                {"key": "id", "label": "id"},
                {"key": "name", "label": "name"},
                {"key": "slug", "label": "slug"},
                {"key": "version", "label": "Версия"},
                {"key": "description", "label": "description"},
            ],
            rows=[
                {
                    "href": f"/surveys/{survey.id}",
                    "cells": {
                        "id": cell(survey.id),
                        "name": cell(survey.name),
                        "slug": cell(survey.slug),
                        "version": cell(version_num),
                        "description": cell(survey.description),
                    },
                }
                for survey, version_num in rows
            ],
            count=count,
            page=page,
            filters=[
                {"name": "name", "label": "name", "value": name},
                {"name": "slug", "label": "slug", "value": slug},
            ],
            filter_values={"name": name, "slug": slug},
        ),
    )


@router.get("/surveys/{survey_id}")
def survey_detail(
    request: Request,
    session: SessionDep,
    user: CurrentUser,
    survey_id: uuid.UUID,
) -> Any:
    try:
        survey = catalog.get_survey(session, survey_id)
        version = catalog.get_latest_survey_version(session, survey_id)
        rows = catalog.get_version_questions(session, version.id)
    except catalog.CatalogNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return templates.TemplateResponse(
        request,
        "survey_detail.html",
        {
            "user": user,
            "survey": survey,
            "version": version,
            "questions": [
                {
                    "order_number": link.order_num,
                    "text": question.text,
                    "scale_name": scale.name,
                }
                for question, scale, link in rows
            ],
        },
    )
