import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from sqlmodel import col, func, select

from app.admin.deps import CurrentUser, SessionDep
from app.admin.templating import PAGE_SIZE, cell, list_context, templates
from app.models import Dog, Survey, SurveySession, SurveyVersion, User
from app.pagination import execute_page, page_window
from app.services import sessions as session_service

router = APIRouter()


def _optional_uuid(value: str) -> uuid.UUID | None:
    if not value:
        return None
    try:
        return uuid.UUID(value)
    except ValueError:
        return None


@router.get("/sessions")
def sessions_page(
    request: Request,
    session: SessionDep,
    user: CurrentUser,
    page: int = 1,
    status: str = "",
    owner_id: str = "",
    dog_id: str = "",
    survey_version_id: str = "",
) -> Any:
    offset, limit, page = page_window(page, PAGE_SIZE)
    filters: list[Any] = []
    if status:
        filters.append(SurveySession.status == status)
    parsed_owner_id = _optional_uuid(owner_id)
    parsed_dog_id = _optional_uuid(dog_id)
    parsed_version_id = _optional_uuid(survey_version_id)
    if parsed_owner_id:
        filters.append(SurveySession.owner_id == parsed_owner_id)
    if parsed_dog_id:
        filters.append(SurveySession.dog_id == parsed_dog_id)
    if parsed_version_id:
        filters.append(SurveySession.survey_version_id == parsed_version_id)
    count_stmt = select(func.count()).select_from(SurveySession)
    stmt = (
        select(  # type: ignore[call-overload]
            SurveySession, User, Dog, SurveyVersion, Survey
        )
        .join(User, col(SurveySession.owner_id) == User.id)
        .join(Dog, col(SurveySession.dog_id) == Dog.id)
        .join(
            SurveyVersion,
            col(SurveySession.survey_version_id) == SurveyVersion.id,
        )
        .join(Survey, col(SurveyVersion.survey_id) == Survey.id)
    )
    if filters:
        count_stmt = count_stmt.where(*filters)
        stmt = stmt.where(*filters)
    rows, count = execute_page(
        session,
        count_stmt,
        stmt.order_by(col(SurveySession.created_at).desc()),
        offset=offset,
        limit=limit,
    )
    return templates.TemplateResponse(
        request,
        "list.html",
        list_context(
            request=request,
            user=user,
            title="Ответы",
            columns=[
                {"key": "id", "label": "id"},
                {"key": "status", "label": "status"},
                {"key": "owner", "label": "Пользователь"},
                {"key": "dog", "label": "Собака"},
                {"key": "survey", "label": "Анкета"},
            ],
            rows=[
                {
                    "href": f"/sessions/{row.id}",
                    "cells": {
                        "id": cell(row.id),
                        "status": cell(row.status),
                        "owner": cell(owner.full_name or owner.email),
                        "dog": cell(dog.name),
                        "survey": f"{survey.name} · v{version.version_num}",
                    },
                }
                for row, owner, dog, version, survey in rows
            ],
            count=count,
            page=page,
            filters=[
                {"name": "status", "label": "status", "value": status},
                {
                    "name": "owner_id",
                    "label": "Пользователь",
                    "value": owner_id,
                },
                {"name": "dog_id", "label": "Собака", "value": dog_id},
                {
                    "name": "survey_version_id",
                    "label": "Версия анкеты",
                    "value": survey_version_id,
                },
            ],
            filter_values={
                "status": status,
                "owner_id": owner_id,
                "dog_id": dog_id,
                "survey_version_id": survey_version_id,
            },
        ),
    )


@router.get("/sessions/{session_id}")
def session_detail(
    request: Request,
    session: SessionDep,
    user: CurrentUser,
    session_id: uuid.UUID,
) -> Any:
    try:
        context = session_service.get_session_context(session, session_id, user)
    except session_service.SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    answers = session_service.get_session_answers(session, context.row)
    rec_groups = session_service.group_recommendations(
        session_service.get_session_recommendations(session, session_id)
    )
    return templates.TemplateResponse(
        request,
        "session_detail.html",
        {
            "user": user,
            "session_row": context.row,
            "survey": context.survey,
            "version": context.version,
            "answers": [
                {
                    "order_number": item.link.order_num,
                    "question_text": item.question.text,
                    "answer": item.display_value,
                    "legend": item.legend,
                }
                for item in answers
            ],
            "rec_groups": rec_groups,
        },
    )
