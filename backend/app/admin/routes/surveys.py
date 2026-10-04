import uuid
from typing import Any

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlmodel import col, func, select

from app.admin.deps import AdminUser, CurrentUser, SessionDep, is_admin
from app.admin.templating import PAGE_SIZE, cell, list_context, templates
from app.models import Question, Scale, Survey, SurveyQuestion, SurveyVersion
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


def _display_num_text(value: int | None) -> str:
    return "" if value is None else str(value)


def _question_fields(
    rows: list[tuple[Question, Scale, SurveyQuestion]],
) -> list[dict[str, str | int]]:
    return [
        {
            "question_id": str(link.question_id),
            "order_number": link.order_num,
            "display_num": _display_num_text(link.display_num),
            "group": link.group,
            "text": question.text,
            "scale_name": scale.name,
        }
        for question, scale, link in rows
    ]


def _survey_detail_response(
    request: Request,
    session: SessionDep,
    user: CurrentUser,
    survey_id: uuid.UUID,
    *,
    error: str | None = None,
    status_code: int = 200,
    questions: list[dict[str, str | int]] | None = None,
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
            "can_edit": is_admin(user),
            "error": error,
            "questions": questions if questions is not None else _question_fields(rows),
        },
        status_code=status_code,
    )


def _parse_display_num(raw: str) -> int | None:
    text = raw.strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError as exc:
        raise catalog.CatalogUpdateError(
            "Отображаемый номер должен быть целым"
        ) from exc


@router.get("/surveys/{survey_id}")
def survey_detail(
    request: Request,
    session: SessionDep,
    user: CurrentUser,
    survey_id: uuid.UUID,
) -> Any:
    return _survey_detail_response(request, session, user, survey_id)


@router.post("/surveys/{survey_id}")
def survey_questions_update(
    request: Request,
    session: SessionDep,
    user: AdminUser,
    survey_id: uuid.UUID,
    question_id: list[str] = Form(default=[]),
    display_num: list[str] = Form(default=[]),
    group: list[str] = Form(default=[]),
) -> Any:
    try:
        version = catalog.get_latest_survey_version(session, survey_id)
        rows = catalog.get_version_questions(session, version.id)
    except catalog.CatalogNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    posted = _question_fields(rows)
    by_id = {item["question_id"]: item for item in posted}
    if (
        len(question_id) != len(display_num)
        or len(question_id) != len(group)
        or len(question_id) != len(posted)
    ):
        return _survey_detail_response(
            request,
            session,
            user,
            survey_id,
            error="Некорректные данные вопросов",
            status_code=400,
        )
    for raw_id, raw_display, raw_group in zip(question_id, display_num, group, strict=True):
        item = by_id.get(raw_id)
        if item is None:
            return _survey_detail_response(
                request,
                session,
                user,
                survey_id,
                error="Некорректные данные вопросов",
                status_code=400,
            )
        item["display_num"] = raw_display
        item["group"] = raw_group
    try:
        updates = [
            (
                uuid.UUID(str(item["question_id"])),
                _parse_display_num(str(item["display_num"])),
                str(item["group"]).strip(),
            )
            for item in posted
        ]
        if any(not group_value for _question, _display, group_value in updates):
            raise catalog.CatalogUpdateError("Группа обязательна")
        catalog.update_survey_question_layout(session, version.id, updates)
    except catalog.CatalogUpdateError as exc:
        session.rollback()
        return _survey_detail_response(
            request,
            session,
            user,
            survey_id,
            error=str(exc),
            status_code=400,
            questions=posted,
        )
    except ValueError as exc:
        session.rollback()
        return _survey_detail_response(
            request,
            session,
            user,
            survey_id,
            error=str(exc),
            status_code=400,
            questions=posted,
        )
    return RedirectResponse(f"/surveys/{survey_id}", status_code=303)
