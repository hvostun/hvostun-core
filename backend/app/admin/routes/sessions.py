import logging
import uuid
from typing import Any
from urllib.parse import urlencode

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlmodel import col, func, select

from app.admin.deps import AdminUser, CurrentUser, SessionDep, SuperUser, is_admin
from app.admin.templating import PAGE_SIZE, cell, list_context, templates
from app.core.config import settings
from app.models import AnswerEvent, Dog, SessionRecommendation, SurveySession
from app.pagination import execute_page, page_window
from app.services import dictionaries as dictionary_service
from app.services import scoring as scoring_service
from app.services import sessions as session_service
from app.services import summary as summary_service

logger = logging.getLogger(__name__)
router = APIRouter()


def _filled_threshold(raw: str | None) -> int:
    if raw is None:
        return 90
    text = raw.strip()
    if not text:
        return 0
    try:
        value = int(text)
    except ValueError:
        return 90
    return min(100, max(0, value))


def _session_location(session_id: uuid.UUID, view: str) -> str:
    if view in {"domains", "flat", "summary"}:
        return f"/sessions/{session_id}?view={view}"
    return f"/sessions/{session_id}"


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
    mine: str | None = None,
    filled: str | None = None,
) -> Any:
    if mine is None:
        query = dict(request.query_params)
        query["mine"] = "no"
        return RedirectResponse(f"/sessions?{urlencode(query)}", status_code=303)
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
    if mine not in {"yes", "no"}:
        mine = ""
    my_recommendation = (
        select(SessionRecommendation.id)
        .where(SessionRecommendation.session_id == SurveySession.id)
        .where(SessionRecommendation.user_id == user.id)
        .exists()
    )
    if mine == "yes":
        filters.append(my_recommendation)
    elif mine == "no":
        filters.append(~my_recommendation)
    filled_min = _filled_threshold(filled)
    show_evaluation_counts = session_service.can_see_evaluation_counts(user)
    expert_queue = session_service.uses_expert_session_queue(user)
    recommendation_users_subquery = session_service.expert_evaluation_count_subquery()
    fill_rates = session_service.answer_rate_subquery()
    user_count = func.coalesce(recommendation_users_subquery.c.user_count, 0)
    count_stmt = select(func.count()).select_from(SurveySession)
    stmt = select(
        SurveySession,
        Dog,
        my_recommendation,
    ).join(Dog, col(SurveySession.dog_id) == Dog.id)
    count_stmt = count_stmt.outerjoin(
        fill_rates,
        col(SurveySession.id) == fill_rates.c.session_id,
    )
    stmt = stmt.outerjoin(
        fill_rates,
        col(SurveySession.id) == fill_rates.c.session_id,
    )
    filters.append(func.coalesce(fill_rates.c.rate, 0) >= filled_min)
    join_counts = (
        recommendation_users_subquery,
        col(SurveySession.id) == recommendation_users_subquery.c.session_id,
    )
    stmt = stmt.outerjoin(*join_counts)
    count_stmt = count_stmt.outerjoin(*join_counts)
    if expert_queue and mine == "no":
        filters.append(user_count < session_service.EXPERT_LIST_EVALUATION_CAP)
    if filters:
        count_stmt = count_stmt.where(*filters)
        stmt = stmt.where(*filters)
    # Rank inside a cluster by evaluation count, then interleave clusters.
    cluster_rank = func.row_number().over(
        partition_by=col(SurveySession.cluster),
        order_by=(user_count.desc(), col(SurveySession.created_at).desc()),
    )
    ordering = (
        cluster_rank.asc(),
        col(SurveySession.cluster).asc().nulls_last(),
        col(SurveySession.created_at).desc(),
    )
    rows, count = execute_page(
        session,
        count_stmt,
        stmt.order_by(*ordering),
        offset=offset,
        limit=limit,
    )
    page_ids = [row.id for row, *_ in rows]
    user_counts = session_service.session_recommendation_user_counts(session, page_ids)
    rates = session_service.answer_rates(session, page_ids)
    columns: list[dict[str, Any]] = [
        {"key": "dog", "label": "Собака"},
        {"key": "answer_rate", "label": "Ответов, %"},
    ]
    if show_evaluation_counts:
        columns.append({"key": "cluster", "label": "Кластер"})
        columns.append({"key": "users", "label": "Оценили"})
    columns.append(
        {
            "key": "has_mine",
            "label": "Моя оценка",
            "type": "checkbox",
        }
    )
    return templates.TemplateResponse(
        request,
        "list.html",
        list_context(
            request=request,
            user=user,
            title="Ответы",
            columns=columns,
            rows=[
                {
                    "href": f"/sessions/{row.id}",
                    "cells": {
                        "dog": cell(dog.name),
                        "answer_rate": (
                            "—" if rates[row.id] is None else cell(rates[row.id]) + " %"
                        ),
                        "cluster": cell(row.cluster) or "—",
                        "users": cell(user_counts[row.id]),
                        "has_mine": has_mine,
                    },
                }
                for row, dog, has_mine in rows
            ],
            count=count,
            page=page,
            filters=[
                {
                    "name": "mine",
                    "type": "select",
                    "label": "Моя оценка",
                    "value": mine,
                    "options": [
                        {"value": "no", "label": "Без моей рекомендации"},
                        {"value": "yes", "label": "Мои рекомендации"},
                        {"value": "", "label": "Все"},
                    ],
                },
                {
                    "name": "filled",
                    "type": "number",
                    "label": "Заполнение, %",
                    "value": str(filled_min),
                },
            ],
            filter_values={
                "mine": mine,
                "filled": str(filled_min),
            },
        ),
    )


@router.get("/answer-events")
def answer_events_page(
    request: Request,
    session: SessionDep,
    user: SuperUser,
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
                {"key": "id", "label": "Идентификатор"},
                {"key": "surveys_session_id", "label": "Сессия"},
                {"key": "question_id", "label": "Вопрос"},
                {"key": "value", "label": "Значение"},
                {"key": "created_at", "label": "Создано"},
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
                    "label": "Сессия",
                    "value": surveys_session_id,
                },
                {
                    "name": "survey_version_id",
                    "label": "Версия анкеты",
                    "value": survey_version_id,
                },
                {
                    "name": "question_id",
                    "label": "Вопрос",
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


def _active_view(requested: str, has_domains: bool) -> str:
    if requested == "summary":
        return "summary"
    if not has_domains or requested == "flat":
        return "flat"
    return "domains"


def _summary_context(
    session: SessionDep,
    context: session_service.SessionContext,
    answers: list[session_service.SessionAnswer],
    scoring: scoring_service.DomainScoring | None,
) -> dict[str, Any]:
    dog_facts = session_service.dog_session_facts(session, context.dog, context.row)
    facts = summary_service.build_facts(session, scoring, answers, dog_facts)
    anonymized = summary_service.anonymize_history(
        dog_facts.get("history") if isinstance(dog_facts.get("history"), str) else None,
        context.owner,
        context.dog,
    )
    stored = summary_service.parse_stored_summary(context.row.summary)
    if stored is not None:
        summary_text = {"narrative": stored.narrative}
        summary_source = "gigachat"
        summary_meta = {
            "model": stored.model,
            "generated_at": stored.generated_at,
        }
        summary_facts = {
            "red_flags": [
                {"text": item.text, "refs": list(item.refs)} for item in facts.red_flags
            ],
            "gaps": list(facts.gaps),
            "dog": list(facts.dog),
            "overview": list(facts.overview),
        }
    else:
        summary_text = {"narrative": ""}
        summary_source = "rules"
        summary_meta = None
        summary_facts = {
            "red_flags": [],
            "gaps": [],
            "dog": [],
            "overview": [],
        }
    return {
        "summary_facts": summary_facts,
        "summary_text": summary_text,
        "summary_source": summary_source,
        "summary_meta": summary_meta,
        "gigachat_enabled": settings.gigachat_enabled,
        "can_generate_summary": False,
        "gigachat_models": [],
        "gigachat_default_model": settings.GIGACHAT_MODEL,
        "anonymized_history": anonymized,
    }


def _session_detail_response(
    request: Request,
    session: SessionDep,
    user: CurrentUser,
    session_id: uuid.UUID,
    *,
    category: str = "",
    answer: str = "",
    view: str = "",
    error: str | None = None,
    status_code: int = 200,
) -> Any:
    try:
        context = session_service.get_session_context(session, session_id, user)
    except session_service.SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    answers = session_service.get_session_answers(session, context.row)
    scoring = scoring_service.score_session(session, answers)
    active_view = _active_view(view, scoring is not None)
    filtered = session_service.filter_session_answers(
        answers, category=category, answer=answer
    )
    blocks = (
        scoring_service.scoring_view(session, scoring)
        if scoring is not None and active_view == "domains"
        else None
    )
    rec_groups = session_service.group_recommendations(
        session_service.get_session_recommendations(session, session_id, user)
    )
    available = session_service.available_recommendations_for_user(
        session,
        session_id=session_id,
        user_id=user.id,
    )
    dog_facts = session_service.dog_session_facts(session, context.dog, context.row)
    can_generate_summary = settings.gigachat_enabled and is_admin(user)
    gigachat_models = dictionary_service.list_gigachat_models(session)
    summary_ctx = (
        _summary_context(session, context, answers, scoring)
        if active_view == "summary"
        else {
            "summary_facts": None,
            "summary_text": None,
            "summary_source": "rules",
            "summary_meta": None,
            "gigachat_enabled": settings.gigachat_enabled,
            "can_generate_summary": False,
            "gigachat_models": [],
            "gigachat_default_model": settings.GIGACHAT_MODEL,
        }
    )
    if active_view == "summary":
        summary_ctx = {
            **summary_ctx,
            "can_generate_summary": can_generate_summary,
            "gigachat_models": [
                {
                    "id": model_id,
                    "label": dictionary_service.gigachat_model_label(session, model_id),
                }
                for model_id in gigachat_models
            ],
            "gigachat_default_model": settings.GIGACHAT_MODEL,
        }
    return templates.TemplateResponse(
        request,
        "session_detail.html",
        {
            "user": user,
            "session_row": context.row,
            "survey": context.survey,
            "version": context.version,
            "dog": dog_facts,
            "answers": [scoring_service.answer_row(session, item) for item in filtered],
            "view": active_view,
            "has_domains": scoring is not None,
            "domain_sections": [] if blocks is None else blocks["domains"],
            "unscored_answers": [] if blocks is None else blocks["unscored"],
            "categories": session_service.session_answer_categories(
                session, [str(item.link.group) for item in answers]
            ),
            "answer_values": session_service.session_answer_values(answers),
            "category": category,
            "answer": answer,
            "unanswered_filter": session_service.UNANSWERED_FILTER,
            "has_questions": bool(answers),
            "rec_groups": rec_groups,
            "has_my_recommendations": any(
                item["user_id"] == user.id
                for group in rec_groups
                for item in group["recommendations"]
            ),
            "can_manage_all_recommendations": (
                session_service.can_manage_all_session_recommendations(user)
            ),
            "available_recommendations": available,
            "error": error,
            **summary_ctx,
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
    view: str = "",
) -> Any:
    return _session_detail_response(
        request,
        session,
        user,
        session_id,
        category=category,
        answer=answer,
        view=view,
    )


@router.post("/sessions/{session_id}/summary")
def generate_session_summary(
    request: Request,
    session: SessionDep,
    user: AdminUser,
    session_id: uuid.UUID,
    model: str = Form(""),
) -> Any:
    if not settings.gigachat_enabled:
        return _session_detail_response(
            request,
            session,
            user,
            session_id,
            view="summary",
            error="GigaChat не настроен",
            status_code=400,
        )
    try:
        context = session_service.get_session_context(session, session_id, user)
    except session_service.SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    allowed = dictionary_service.list_gigachat_models(session)
    chosen = model.strip()
    if chosen and chosen not in allowed:
        return _session_detail_response(
            request,
            session,
            user,
            session_id,
            view="summary",
            error="Неизвестная модель GigaChat",
            status_code=400,
        )
    outcome = summary_service.generate_and_store_summary(
        session,
        context,
        generated_by=user.id,
        force=True,
        model=chosen or None,
    )
    if outcome.status == "error":
        logger.warning(
            "session summary failed session_id=%s detail=%s",
            session_id,
            outcome.detail,
        )
        if outcome.detail.startswith("GigaChat"):
            error = outcome.detail
            status_code = 502
        elif outcome.detail == "ответ не прошёл проверку":
            error = "Сводку не удалось проверить"
            status_code = 400
        else:
            error = outcome.detail
            status_code = 400
        return _session_detail_response(
            request,
            session,
            user,
            session_id,
            view="summary",
            error=error,
            status_code=status_code,
        )
    return RedirectResponse(f"/sessions/{session_id}?view=summary", status_code=303)


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
    name: str = Form(""),
    description: str = Form(""),
    view: str = Form(""),
) -> Any:
    if recomendation_id == "new":
        try:
            session_service.create_session_recommendation(
                session,
                session_id=session_id,
                current_user=user,
                name=name,
                description=description,
            )
        except session_service.SessionNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except session_service.SessionRecommendationError as exc:
            return _session_detail_response(
                request,
                session,
                user,
                session_id,
                view=view,
                error=str(exc),
                status_code=400,
            )
        return RedirectResponse(_session_location(session_id, view), status_code=303)
    try:
        parsed_id = uuid.UUID(recomendation_id)
    except ValueError:
        return _session_detail_response(
            request,
            session,
            user,
            session_id,
            view=view,
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
            view=view,
            error=str(exc),
            status_code=400,
        )
    return RedirectResponse(_session_location(session_id, view), status_code=303)


@router.post("/sessions/{session_id}/recommendations/{recommendation_id}/delete")
def delete_session_recommendation(
    session: SessionDep,
    user: CurrentUser,
    session_id: uuid.UUID,
    recommendation_id: uuid.UUID,
    view: str = Form(""),
) -> RedirectResponse:
    try:
        session_service.delete_session_recommendation(
            session,
            session_id=session_id,
            current_user=user,
            recommendation_id=recommendation_id,
        )
    except session_service.SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except session_service.SessionRecommendationPermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return RedirectResponse(_session_location(session_id, view), status_code=303)


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
    view: str = Form(""),
) -> Any:
    if not (len(recommendation_id) == len(chart_number) == len(weight) == len(comment)):
        return _session_detail_response(
            request,
            session,
            user,
            session_id,
            view=view,
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
            view=view,
            error=str(exc),
            status_code=400,
        )
    except session_service.SessionRecommendationPermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError:
        return _session_detail_response(
            request,
            session,
            user,
            session_id,
            view=view,
            error="Некорректные данные рекомендаций",
            status_code=400,
        )
    return RedirectResponse(_session_location(session_id, view), status_code=303)
