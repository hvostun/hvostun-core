from typing import Any

from fastapi import APIRouter, Request
from sqlmodel import col, func, select

from app.admin.deps import SessionDep, SuperUser
from app.admin.templating import PAGE_SIZE, cell, list_context, templates
from app.models import Owner, Recommendation, User
from app.pagination import execute_page, page_window

router = APIRouter()


def _render_list(
    *,
    request: Request,
    session: SessionDep,
    user: User,
    page: int,
    title: str,
    model: type[Any],
    statement: Any,
    filters_sql: list[Any],
    columns: list[dict[str, str]],
    row_cells: Any,
    filters: list[dict[str, str]],
    filter_values: dict[str, str],
) -> Any:
    offset, limit, page = page_window(page, PAGE_SIZE)
    count_stmt = select(func.count()).select_from(model)
    if filters_sql:
        count_stmt = count_stmt.where(*filters_sql)
        statement = statement.where(*filters_sql)
    rows, count = execute_page(
        session,
        count_stmt,
        statement,
        offset=offset,
        limit=limit,
    )
    return templates.TemplateResponse(
        request,
        "list.html",
        list_context(
            request=request,
            user=user,
            title=title,
            columns=columns,
            rows=[{"href": None, "cells": row_cells(row)} for row in rows],
            count=count,
            page=page,
            filters=filters,
            filter_values=filter_values,
        ),
    )


@router.get("/owners")
def owners_page(
    request: Request,
    session: SessionDep,
    user: SuperUser,
    page: int = 1,
    name: str = "",
    email: str = "",
    phone: str = "",
) -> Any:
    filters_sql: list[Any] = []
    if name:
        filters_sql.append(col(Owner.name).ilike(f"%{name}%"))
    if email:
        filters_sql.append(col(Owner.email).ilike(f"%{email}%"))
    if phone:
        filters_sql.append(col(Owner.phone).ilike(f"%{phone}%"))
    return _render_list(
        request=request,
        session=session,
        user=user,
        page=page,
        title="Владельцы",
        model=Owner,
        statement=select(Owner).order_by(col(Owner.created_at).desc()),
        filters_sql=filters_sql,
        columns=[
            {"key": "id", "label": "id"},
            {"key": "name", "label": "name"},
            {"key": "email", "label": "email"},
            {"key": "phone", "label": "phone"},
            {"key": "contact", "label": "contact"},
        ],
        row_cells=lambda row: {
            "id": cell(row.id),
            "name": cell(row.name),
            "email": cell(row.email),
            "phone": cell(row.phone),
            "contact": cell(row.contact),
        },
        filters=[
            {"name": "name", "label": "name", "value": name},
            {"name": "email", "label": "email", "value": email},
            {"name": "phone", "label": "phone", "value": phone},
        ],
        filter_values={"name": name, "email": email, "phone": phone},
    )


@router.get("/recommendations")
def recommendations_page(
    request: Request,
    session: SessionDep,
    user: SuperUser,
    page: int = 1,
    name: str = "",
    slug: str = "",
) -> Any:
    filters_sql: list[Any] = []
    if name:
        filters_sql.append(col(Recommendation.name).ilike(f"%{name}%"))
    if slug:
        filters_sql.append(col(Recommendation.slug).ilike(f"%{slug}%"))
    return _render_list(
        request=request,
        session=session,
        user=user,
        page=page,
        title="Рекомендации",
        model=Recommendation,
        statement=select(Recommendation).order_by(
            col(Recommendation.slug), col(Recommendation.created_at)
        ),
        filters_sql=filters_sql,
        columns=[
            {"key": "id", "label": "id"},
            {"key": "name", "label": "name"},
            {"key": "slug", "label": "slug"},
            {"key": "description", "label": "description"},
        ],
        row_cells=lambda row: {
            "id": cell(row.id),
            "name": cell(row.name),
            "slug": cell(row.slug),
            "description": cell(row.description),
        },
        filters=[
            {"name": "name", "label": "name", "value": name},
            {"name": "slug", "label": "slug", "value": slug},
        ],
        filter_values={"name": name, "slug": slug},
    )


@router.get("/users")
def users_page(
    request: Request,
    session: SessionDep,
    user: SuperUser,
    page: int = 1,
    email: str = "",
    full_name: str = "",
) -> Any:
    filters_sql: list[Any] = []
    if email:
        filters_sql.append(col(User.email).ilike(f"%{email}%"))
    if full_name:
        filters_sql.append(col(User.full_name).ilike(f"%{full_name}%"))
    return _render_list(
        request=request,
        session=session,
        user=user,
        page=page,
        title="Администраторы",
        model=User,
        statement=select(User).order_by(col(User.created_at).desc()),
        filters_sql=filters_sql,
        columns=[
            {"key": "id", "label": "id"},
            {"key": "email", "label": "email"},
            {"key": "full_name", "label": "full_name"},
            {"key": "group", "label": "group"},
            {"key": "is_superuser", "label": "is_superuser"},
            {"key": "is_active", "label": "is_active"},
        ],
        row_cells=lambda row: {
            "id": cell(row.id),
            "email": cell(row.email),
            "full_name": cell(row.full_name),
            "group": cell(row.group),
            "is_superuser": cell(row.is_superuser),
            "is_active": cell(row.is_active),
        },
        filters=[
            {"name": "email", "label": "email", "value": email},
            {
                "name": "full_name",
                "label": "full_name",
                "value": full_name,
            },
        ],
        filter_values={"email": email, "full_name": full_name},
    )
