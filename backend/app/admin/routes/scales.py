import json
import uuid
from typing import Any

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlmodel import col, func, select

from app.admin.deps import AdminUser, CurrentUser, SessionDep, is_admin
from app.admin.templating import PAGE_SIZE, cell, list_context, templates
from app.models import Scale, ScaleType
from app.models.catalog_immutability import (
    DomainValueValidationError,
    JSONBValidationError,
)
from app.pagination import execute_page, page_window
from app.services import catalog

router = APIRouter()


def _format_config(config: object) -> str:
    if not config:
        return ""
    return json.dumps(config, ensure_ascii=False, indent=2)


def _parse_config(raw: str) -> dict[str, object] | None:
    text = raw.strip()
    if not text:
        return None
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("config must be a JSON object")
    return parsed


def _scale_detail_response(
    request: Request,
    user: CurrentUser,
    scale: Scale,
    *,
    error: str | None = None,
    status_code: int = 200,
    form: dict[str, str] | None = None,
) -> Any:
    return templates.TemplateResponse(
        request,
        "scale_detail.html",
        {
            "user": user,
            "scale": scale,
            "can_edit": is_admin(user),
            "scale_types": [item.value for item in ScaleType],
            "config_text": form["config"] if form else _format_config(scale.config),
            "form_name": form["name"] if form else scale.name,
            "form_description": (
                form["description"] if form else (scale.description or "")
            ),
            "form_type": form["type"] if form else scale.type,
            "error": error,
        },
        status_code=status_code,
    )


@router.get("/scales")
def scales_page(
    request: Request,
    session: SessionDep,
    user: CurrentUser,
    page: int = 1,
    name: str = "",
    type: str = "",
) -> Any:
    offset, limit, page = page_window(page, PAGE_SIZE)
    filters: list[Any] = []
    if name:
        filters.append(col(Scale.name).ilike(f"%{name}%"))
    if type:
        filters.append(Scale.type == type)
    count_stmt = select(func.count()).select_from(Scale)
    stmt = select(Scale)
    if filters:
        count_stmt = count_stmt.where(*filters)
        stmt = stmt.where(*filters)
    rows, count = execute_page(
        session,
        count_stmt,
        stmt.order_by(col(Scale.name), col(Scale.created_at)),
        offset=offset,
        limit=limit,
    )
    return templates.TemplateResponse(
        request,
        "list.html",
        list_context(
            request=request,
            user=user,
            title="Шкалы",
            columns=[
                {"key": "id", "label": "id"},
                {"key": "name", "label": "name"},
                {"key": "type", "label": "type"},
                {"key": "description", "label": "description"},
            ],
            rows=[
                {
                    "href": f"/scales/{row.id}",
                    "cells": {
                        "id": cell(row.id),
                        "name": cell(row.name),
                        "type": cell(row.type),
                        "description": cell(row.description),
                    },
                }
                for row in rows
            ],
            count=count,
            page=page,
            filters=[
                {"name": "name", "label": "name", "value": name},
                {"name": "type", "label": "type", "value": type},
            ],
            filter_values={"name": name, "type": type},
        ),
    )


@router.get("/scales/{scale_id}")
def scale_detail(
    request: Request,
    session: SessionDep,
    user: CurrentUser,
    scale_id: uuid.UUID,
) -> Any:
    try:
        scale = catalog.get_scale(session, scale_id)
    except catalog.CatalogNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _scale_detail_response(request, user, scale)


@router.post("/scales/{scale_id}")
def scale_update(
    request: Request,
    session: SessionDep,
    user: AdminUser,
    scale_id: uuid.UUID,
    name: str = Form(""),
    description: str = Form(""),
    type: str = Form(""),
    config: str = Form(""),
) -> Any:
    try:
        scale = catalog.get_scale(session, scale_id)
    except catalog.CatalogNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    form = {
        "name": name,
        "description": description,
        "type": type,
        "config": config,
    }
    if not name.strip():
        return _scale_detail_response(
            request,
            user,
            scale,
            error="Название обязательно",
            status_code=400,
            form=form,
        )
    try:
        scale_type = ScaleType(type)
        parsed_config = _parse_config(config)
        catalog.update_scale(
            session,
            scale_id,
            name=name.strip(),
            description=description.strip() or None,
            type=scale_type,
            config=parsed_config,
        )
    except (ValueError, json.JSONDecodeError) as exc:
        return _scale_detail_response(
            request,
            user,
            scale,
            error=str(exc),
            status_code=400,
            form=form,
        )
    except (JSONBValidationError, DomainValueValidationError) as exc:
        session.rollback()
        return _scale_detail_response(
            request,
            user,
            scale,
            error=str(exc),
            status_code=400,
            form=form,
        )
    return RedirectResponse(f"/scales/{scale_id}", status_code=303)
