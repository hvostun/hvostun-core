import json
from typing import Any

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlmodel import col, func, select

from app.admin.deps import CurrentUser, SessionDep
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
        raise ValueError("value обязателен")
    return json.loads(text)


def _detail_response(
    request: Request,
    user: CurrentUser,
    row: Dictionary,
    *,
    error: str | None = None,
    status_code: int = 200,
    value_text: str | None = None,
) -> Any:
    return templates.TemplateResponse(
        request,
        "dictionary_detail.html",
        {
            "user": user,
            "row": row,
            "value_text": (
                value_text if value_text is not None else _format_value(row.value)
            ),
            "error": error,
        },
        status_code=status_code,
    )


@router.get("/dictionaries")
def dictionaries_page(
    request: Request,
    session: SessionDep,
    user: CurrentUser,
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
                {"key": "key", "label": "key"},
                {"key": "value", "label": "value"},
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
            filters=[{"name": "key", "label": "key", "value": key}],
            filter_values={"key": key},
        ),
    )


@router.get("/dictionaries/{key}")
def dictionary_detail(
    request: Request,
    session: SessionDep,
    user: CurrentUser,
    key: str,
) -> Any:
    try:
        row = dictionary_service.get_dictionary(session, key)
    except dictionary_service.DictionaryNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _detail_response(request, user, row)


@router.post("/dictionaries/{key}")
def dictionary_update(
    request: Request,
    session: SessionDep,
    user: CurrentUser,
    key: str,
    value: str = Form(""),
) -> Any:
    try:
        row = dictionary_service.get_dictionary(session, key)
    except dictionary_service.DictionaryNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    try:
        parsed = _parse_value(value)
        dictionary_service.update_dictionary(
            session, key, value=parsed, updated_by=user
        )
    except (ValueError, json.JSONDecodeError) as exc:
        return _detail_response(
            request,
            user,
            row,
            error=(
                "Некорректный JSON"
                if isinstance(exc, json.JSONDecodeError)
                else str(exc)
            ),
            status_code=400,
            value_text=value,
        )
    return RedirectResponse(f"/dictionaries/{key}", status_code=303)
