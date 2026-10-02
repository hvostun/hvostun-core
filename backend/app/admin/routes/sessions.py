import uuid
from typing import Any

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlmodel import col, func, select

from app.admin.deps import CurrentUser, SessionDep
from app.admin.templating import PAGE_SIZE, cell, list_context, templates
from app.models import AnswerEvent, Dog, Survey, SurveySession, SurveyVersion, User
from app.pagination import execute_page, page_window
from app.services import dictionaries as dictionary_service
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
    rec_counts = session_service.session_recommendation_counts(
        session, [row.id for row, *_ in rows]
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
                {"key": "recommendations", "label": "Рекомендации"},
                {"key": "users", "label": "Пользователи"},
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
                        "recommendations": cell(rec_counts[row.id][0]),
                        "users": cell(rec_counts[row.id][1]),
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


@router.get("/answer-events")
def answer_events_page(
    request: Request,
    session: SessionDep,
    user: CurrentUser,
    page: int = 1,
    surveys_session_id: str = "",
    survey_version_id: str = "",
    question_id: str = "",
) -> Any:
    offset, limit, page = page_window(page, PAGE_SIZE)
    filters = session_service.answer_event_filters(
        surveys_session_id=_optional_uuid(surveys_session_id),
        survey_version_id=_optional_uuid(survey_version_id),
        question_id=_optional_uuid(question_id),
    )
    count_stmt = select(func.count()).select_from(AnswerEvent)
    stmt = select(AnswerEvent)
    if filters:
        count_stmt = count_stmt.where(*filters)
        stmt = stmt.where(*filters)
    rows, count = execute_page(
        session,
        count_stmt,
        stmt.order_by(col(AnswerEvent.created_at).desc()),
        offset=offset,
        limit=limit,
    )
    return templates.TemplateResponse(
        request,
        "list.html",
        list_context(
            request=request,
            user=user,
            title="События ответов",
            columns=[
                {"key": "id", "label": "id"},
                {"key": "surveys_session_id", "label": "session"},
                {"key": "question_id", "label": "question"},
                {"key": "value", "label": "value"},
                {"key": "created_at", "label": "created_at"},
            ],
            rows=[
                {
                    "href": f"/sessions/{row.surveys_session_id}",
                    "cells": {
                        "id": cell(row.id),
                        "surveys_session_id": cell(row.surveys_session_id),
                        "question_id": cell(row.question_id),
                        "value": cell(row.value),
                        "created_at": cell(row.created_at),
                    },
                }
                for row in rows
            ],
            count=count,
            page=page,
            filters=[
                {
                    "name": "surveys_session_id",
                    "label": "session",
                    "value": surveys_session_id,
                },
                {
                    "name": "survey_version_id",
                    "label": "version",
                    "value": survey_version_id,
                },
                {
                    "name": "question_id",
                    "label": "question",
                    "value": question_id,
                },
            ],
            filter_values={
                "surveys_session_id": surveys_session_id,
                "survey_version_id": survey_version_id,
                "question_id": question_id,
            },
        ),
    )


def _session_detail_response(
    request: Request,
    session: SessionDep,
    user: CurrentUser,
    session_id: uuid.UUID,
    *,
    category: str = "",
    answer: str = "",
    error: str | None = None,
    status_code: int = 200,
) -> Any:
    try:
        context = session_service.get_session_context(session, session_id, user)
    except session_service.SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    answers = session_service.get_session_answers(session, context.row)
    filtered = session_service.filter_session_answers(
        answers, category=category, answer=answer
    )
    rec_groups = session_service.group_recommendations(
        session_service.get_session_recommendations(session, session_id)
    )
    available = session_service.available_recommendations_for_user(
        session,
        session_id=session_id,
        user_id=user.id,
    )
    return templates.TemplateResponse(
        request,
        "session_detail.html",
        {
            "user": user,
            "session_row": context.row,
            "survey": context.survey,
            "version": context.version,
            "dog": session_service.dog_session_facts(
                session, context.dog, context.row
            ),
            "answers": [
                {
                    "order_number": item.link.order_num,
                    "question_text": item.question.text,
                    "category_name": dictionary_service.label_for(
                        session,
                        dictionary_service.SURVEYS_QUESTIONS_GROUP_KEY,
                        item.link.group,
                    ),
                    "answer": item.display_value,
                    "legend": item.legend,
                    "show_bar": item.progress["show_bar"],
                    "bar_percent": item.progress["percent"],
                    "bar_color": item.progress["color"],
                }
                for item in filtered
            ],
            "categories": session_service.session_answer_categories(session),
            "answer_values": session_service.session_answer_values(answers),
            "category": category,
            "answer": answer,
            "unanswered_filter": session_service.UNANSWERED_FILTER,
            "has_questions": bool(answers),
            "rec_groups": rec_groups,
            "available_recommendations": available,
            "error": error,
        },
        status_code=status_code,
    )


@router.get("/sessions/{session_id}")
def session_detail(
    request: Request,
    session: SessionDep,
    user: CurrentUser,
    session_id: uuid.UUID,
    category: str = "",
    answer: str = "",
) -> Any:
    return _session_detail_response(
        request,
        session,
        user,
        session_id,
        category=category,
        answer=answer,
    )


@router.post("/sessions/{session_id}/recommendations")
def add_session_recommendation(
    request: Request,
    session: SessionDep,
    user: CurrentUser,
    session_id: uuid.UUID,
    recomendation_id: str = Form(""),
    chart_number: str = Form(""),
    weight: str = Form(""),
    comment: str = Form(""),
) -> Any:
    try:
        parsed_id = uuid.UUID(recomendation_id)
    except ValueError:
        return _session_detail_response(
            request,
            session,
            user,
            session_id,
            error="Выберите рекомендацию",
            status_code=400,
        )
    try:
        session_service.add_session_recommendation(
            session,
            session_id=session_id,
            current_user=user,
            recomendation_id=parsed_id,
            comment=comment,
            chart_number=session_service.parse_chart_number(chart_number),
            weight=session_service.parse_weight(weight),
        )
    except session_service.SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except session_service.SessionRecommendationError as exc:
        return _session_detail_response(
            request,
            session,
            user,
            session_id,
            error=str(exc),
            status_code=400,
        )
    return RedirectResponse(f"/sessions/{session_id}", status_code=303)


@router.post("/sessions/{session_id}/recommendations/save")
def save_session_recommendations(
    request: Request,
    session: SessionDep,
    user: CurrentUser,
    session_id: uuid.UUID,
    recommendation_id: list[str] = Form(default=[]),
    chart_number: list[str] = Form(default=[]),
    weight: list[str] = Form(default=[]),
    comment: list[str] = Form(default=[]),
) -> Any:
    if not (
        len(recommendation_id)
        == len(chart_number)
        == len(weight)
        == len(comment)
    ):
        return _session_detail_response(
            request,
            session,
            user,
            session_id,
            error="Некорректные данные рекомендаций",
            status_code=400,
        )
    try:
        updates = [
            (
                uuid.UUID(row_id),
                session_service.parse_chart_number(chart),
                session_service.parse_weight(weight_value),
                text,
            )
            for row_id, chart, weight_value, text in zip(
                recommendation_id,
                chart_number,
                weight,
                comment,
                strict=True,
            )
        ]
        session_service.update_session_recommendations(
            session,
            session_id=session_id,
            current_user=user,
            updates=updates,
        )
    except session_service.SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except session_service.SessionRecommendationError as exc:
        return _session_detail_response(
            request,
            session,
            user,
            session_id,
            error=str(exc),
            status_code=400,
        )
    except ValueError:
        return _session_detail_response(
            request,
            session,
            user,
            session_id,
            error="Некорректные данные рекомендаций",
            status_code=400,
        )
    return RedirectResponse(f"/sessions/{session_id}", status_code=303)
