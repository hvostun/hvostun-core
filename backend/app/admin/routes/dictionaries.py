import json
from typing import Any

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlmodel import col, func, select

from app.admin.deps import CurrentUser, SessionDep, SuperUser
from app.admin.templating import PAGE_SIZE, cell, list_context, templates
from app.models import Dictionary
from app.pagination import execute_page, page_window
from app.services import dictionaries as dictionary_service

router = APIRouter()


def _format_value(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def _preview_value(value: object) -> str:
    text = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if len(text) <= 80:
        return text
    return text[:77] + "..."


def _parse_value(raw: str) -> Any:
    text = raw.strip()
    if not text:
        raise ValueError("Значение обязательно")
    return json.loads(text)


def _form_response(
    request: Request,
    user: CurrentUser,
    *,
    is_create: bool,
    key: str = "",
    value_text: str = "{}",
    error: str | None = None,
    status_code: int = 200,
) -> Any:
    return templates.TemplateResponse(
        request,
        "dictionary_form.html",
        {
            "user": user,
            "is_create": is_create,
            "key": key,
            "value_text": value_text,
            "error": error,
        },
        status_code=status_code,
    )


def _json_error_message(exc: Exception) -> str:
    if isinstance(exc, json.JSONDecodeError):
        return "Некорректный JSON"
    return str(exc)


@router.get("/dictionaries")
def dictionaries_page(
    request: Request,
    session: SessionDep,
    user: SuperUser,
    page: int = 1,
    key: str = "",
) -> Any:
    offset, limit, page = page_window(page, PAGE_SIZE)
    filters: list[Any] = []
    if key:
        filters.append(col(Dictionary.key).ilike(f"%{key}%"))
    count_stmt = select(func.count()).select_from(Dictionary)
    stmt = select(Dictionary)
    if filters:
        count_stmt = count_stmt.where(*filters)
        stmt = stmt.where(*filters)
    rows, count = execute_page(
        session,
        count_stmt,
        stmt.order_by(col(Dictionary.key)),
        offset=offset,
        limit=limit,
    )
    return templates.TemplateResponse(
        request,
        "list.html",
        list_context(
            request=request,
            user=user,
            title="Справочники",
            columns=[
                {"key": "key", "label": "Ключ"},
                {"key": "value", "label": "Значение"},
            ],
            rows=[
                {
                    "href": f"/dictionaries/{row.key}",
                    "cells": {
                        "key": cell(row.key),
                        "value": cell(_preview_value(row.value)),
                    },
                }
                for row in rows
            ],
            count=count,
            page=page,
            filters=[{"name": "key", "label": "Ключ", "value": key}],
            filter_values={"key": key},
            create_href="/dictionaries/new",
            create_label="Создать",
        ),
    )


@router.get("/dictionaries/new")
def dictionary_new(request: Request, user: SuperUser) -> Any:
    return _form_response(request, user, is_create=True)


@router.post("/dictionaries/new")
def dictionary_create(
    request: Request,
    session: SessionDep,
    user: SuperUser,
    key: str = Form(""),
    value: str = Form("{}"),
) -> Any:
    try:
        parsed = _parse_value(value)
        created = dictionary_service.create_dictionary(
            session, key=key, value=parsed, created_by=user
        )
    except (
        ValueError,
        json.JSONDecodeError,
        dictionary_service.DictionaryConflictError,
    ) as exc:
        return _form_response(
            request,
            user,
            is_create=True,
            key=key.strip(),
            value_text=value,
            error=_json_error_message(exc),
            status_code=400,
        )
    return RedirectResponse(f"/dictionaries/{created.key}", status_code=303)


@router.get("/dictionaries/{key}")
def dictionary_detail(
    request: Request,
    session: SessionDep,
    user: SuperUser,
    key: str,
) -> Any:
    try:
        row = dictionary_service.get_dictionary(session, key)
    except dictionary_service.DictionaryNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _form_response(
        request,
        user,
        is_create=False,
        key=row.key,
        value_text=_format_value(row.value),
    )


@router.post("/dictionaries/{key}")
def dictionary_update(
    request: Request,
    session: SessionDep,
    user: SuperUser,
    key: str,
    value: str = Form(""),
) -> Any:
    try:
        dictionary_service.get_dictionary(session, key)
    except dictionary_service.DictionaryNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    try:
        parsed = _parse_value(value)
        dictionary_service.update_dictionary(
            session, key, value=parsed, updated_by=user
        )
    except (ValueError, json.JSONDecodeError) as exc:
        return _form_response(
            request,
            user,
            is_create=False,
            key=key,
            value_text=value,
            error=_json_error_message(exc),
            status_code=400,
        )
    return RedirectResponse(f"/dictionaries/{key}", status_code=303)
