from typing import Any

from fastapi import APIRouter, Request
from sqlmodel import col, func, select

from app.admin.deps import CurrentUser, SessionDep
from app.admin.templating import PAGE_SIZE, cell, list_context, templates
from app.models import Dog, Owner, Shelter
from app.pagination import execute_page, page_window

router = APIRouter()


@router.get("/dogs")
def dogs_page(
    request: Request,
    session: SessionDep,
    user: CurrentUser,
    page: int = 1,
    name: str = "",
    status: str = "",
) -> Any:
    offset, limit, page = page_window(page, PAGE_SIZE)
    filters: list[Any] = []
    if name:
        filters.append(col(Dog.name).ilike(f"%{name}%"))
    if status:
        filters.append(Dog.status == status)
    count_stmt = select(func.count()).select_from(Dog)
    stmt = (
        select(Dog, Owner, Shelter)
        .outerjoin(Owner, col(Dog.owner_id) == Owner.id)
        .outerjoin(Shelter, col(Dog.shelter_id) == Shelter.id)
    )
    if filters:
        count_stmt = count_stmt.where(*filters)
        stmt = stmt.where(*filters)
    rows, count = execute_page(
        session,
        count_stmt,
        stmt.order_by(col(Dog.created_at).desc()),
        offset=offset,
        limit=limit,
    )
    return templates.TemplateResponse(
        request,
        "list.html",
        list_context(
            request=request,
            user=user,
            title="Собаки",
            columns=[
                {"key": "name", "label": "name"},
                {"key": "status", "label": "status"},
                {"key": "sex", "label": "sex"},
                {"key": "breed", "label": "breed"},
                {"key": "shelter", "label": "Приют"},
                {"key": "owner", "label": "Владелец"},
            ],
            rows=[
                {
                    "href": None,
                    "cells": {
                        "name": cell(dog.name),
                        "status": cell(dog.status),
                        "sex": cell(dog.sex),
                        "breed": cell(dog.breed),
                        "shelter": cell(shelter.name if shelter else None),
                        "owner": cell(owner.name if owner else None),
                    },
                }
                for dog, owner, shelter in rows
            ],
            count=count,
            page=page,
            filters=[
                {"name": "name", "label": "name", "value": name},
                {"name": "status", "label": "status", "value": status},
            ],
            filter_values={"name": name, "status": status},
        ),
    )
