import uuid
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlmodel import col, func, select

from app.admin.deps import SessionDep, SuperUser
from app.admin.templating import PAGE_SIZE, cell, list_context, templates
from app.models import Owner, Recommendation, User, UserGroup
from app.pagination import execute_page, page_window
from app.services import users as user_service

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
    row_href: Callable[[Any], str | None] | None = None,
    create_href: str | None = None,
    create_label: str | None = None,
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
            rows=[
                {
                    "href": row_href(row) if row_href else None,
                    "cells": row_cells(row),
                }
                for row in rows
            ],
            count=count,
            page=page,
            filters=filters,
            filter_values=filter_values,
            create_href=create_href,
            create_label=create_label,
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
            {"key": "name", "label": "name"},
            {"key": "description", "label": "description"},
        ],
        row_cells=lambda row: {
            "name": cell(row.name),
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
            {"key": "email", "label": "email"},
            {"key": "full_name", "label": "full_name"},
            {"key": "group", "label": "group"},
            {"key": "is_superuser", "label": "is_superuser"},
            {"key": "is_active", "label": "is_active"},
        ],
        row_cells=lambda row: {
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
        row_href=lambda row: f"/users/{row.id}",
        create_href="/users/new",
        create_label="Создать администратора",
    )


def _user_form(
    *,
    email: str = "",
    full_name: str = "",
    group: str = UserGroup.EXPERT,
    phone: str = "",
    contact: str = "",
    is_active: str = "true",
    is_superuser: str = "false",
    password: str = "",
) -> dict[str, str]:
    return {
        "email": email,
        "full_name": full_name,
        "group": group,
        "phone": phone,
        "contact": contact,
        "is_active": is_active,
        "is_superuser": is_superuser,
        "password": password,
    }


def _user_form_from_row(row: User) -> dict[str, str]:
    return _user_form(
        email=row.email,
        full_name=row.full_name or "",
        group=row.group,
        phone=row.phone or "",
        contact=row.contact or "",
        is_active="true" if row.is_active else "false",
        is_superuser="true" if row.is_superuser else "false",
    )


def _user_form_response(
    request: Request,
    user: SuperUser,
    *,
    form: dict[str, str],
    target: User | None = None,
    error: str | None = None,
    status_code: int = 200,
) -> Any:
    return templates.TemplateResponse(
        request,
        "user_form.html",
        {
            "user": user,
            "target": target,
            "form": form,
            "groups": [item.value for item in UserGroup],
            "error": error,
            "is_create": target is None,
        },
        status_code=status_code,
    )


@router.get("/users/new")
def user_new(request: Request, user: SuperUser) -> Any:
    return _user_form_response(request, user, form=_user_form())


@router.post("/users/new")
def user_create(
    request: Request,
    session: SessionDep,
    user: SuperUser,
    email: str = Form(""),
    password: str = Form(""),
    full_name: str = Form(""),
    group: str = Form(UserGroup.EXPERT),
    phone: str = Form(""),
    contact: str = Form(""),
    is_active: str = Form("true"),
    is_superuser: str = Form("false"),
) -> Any:
    form = _user_form(
        email=email,
        full_name=full_name,
        group=group,
        phone=phone,
        contact=contact,
        is_active=is_active,
        is_superuser=is_superuser,
        password=password,
    )
    try:
        created = user_service.create_admin_user(
            session,
            email=email,
            password=password,
            full_name=full_name,
            group=group,
            phone=phone,
            contact=contact,
            is_active=is_active,
            is_superuser=is_superuser,
        )
    except user_service.UserFormError as exc:
        return _user_form_response(
            request, user, form=form, error=str(exc), status_code=400
        )
    return RedirectResponse(f"/users/{created.id}", status_code=303)


@router.get("/users/{user_id}")
def user_detail(
    request: Request,
    session: SessionDep,
    user: SuperUser,
    user_id: uuid.UUID,
) -> Any:
    try:
        target = user_service.get_user(session, user_id)
    except user_service.UserNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _user_form_response(request, user, form=_user_form_from_row(target), target=target)


@router.post("/users/{user_id}")
def user_update(
    request: Request,
    session: SessionDep,
    user: SuperUser,
    user_id: uuid.UUID,
    email: str = Form(""),
    password: str = Form(""),
    full_name: str = Form(""),
    group: str = Form(UserGroup.EXPERT),
    phone: str = Form(""),
    contact: str = Form(""),
    is_active: str = Form("true"),
    is_superuser: str = Form("false"),
) -> Any:
    try:
        target = user_service.get_user(session, user_id)
    except user_service.UserNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    form = _user_form(
        email=email,
        full_name=full_name,
        group=group,
        phone=phone,
        contact=contact,
        is_active=is_active,
        is_superuser=is_superuser,
        password=password,
    )
    try:
        user_service.update_admin_user(
            session,
            user_id=user_id,
            current_user=user,
            email=email,
            password=password,
            full_name=full_name,
            group=group,
            phone=phone,
            contact=contact,
            is_active=is_active,
            is_superuser=is_superuser,
        )
    except user_service.UserFormError as exc:
        return _user_form_response(
            request,
            user,
            form=form,
            target=target,
            error=str(exc),
            status_code=400,
        )
    return RedirectResponse(f"/users/{user_id}", status_code=303)
