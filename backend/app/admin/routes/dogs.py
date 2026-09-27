import uuid
from datetime import date
from typing import Any

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlmodel import col, func, select

from app.admin.deps import CurrentUser, SessionDep
from app.admin.templating import PAGE_SIZE, cell, list_context, templates
from app.models import Dog, DogStatus, Owner, Shelter
from app.models.catalog_immutability import DomainValueValidationError
from app.pagination import execute_page, page_window
from app.services import dogs as dog_service

router = APIRouter()


def _optional_uuid(value: str) -> uuid.UUID | None:
    text = value.strip()
    if not text:
        return None
    return uuid.UUID(text)


def _optional_date(value: str) -> date | None:
    text = value.strip()
    if not text:
        return None
    return date.fromisoformat(text)


def _optional_bool(value: str) -> bool | None:
    if value == "true":
        return True
    if value == "false":
        return False
    return None


def _form_values(
    *,
    name: str,
    sex: str,
    neutered: str,
    status: str,
    description: str,
    shelter_id: str,
    assigned_volunteer_id: str,
    owner_id: str,
    birthday: str,
    status_at: str,
    breed: str,
    mixed: str,
) -> dict[str, str]:
    return {
        "name": name,
        "sex": sex,
        "neutered": neutered,
        "status": status,
        "description": description,
        "shelter_id": shelter_id,
        "assigned_volunteer_id": assigned_volunteer_id,
        "owner_id": owner_id,
        "birthday": birthday,
        "status_at": status_at,
        "breed": breed,
        "mixed": mixed,
    }


def _dog_form_from_row(dog: Dog) -> dict[str, str]:
    return {
        "name": dog.name,
        "sex": dog.sex or "",
        "neutered": "" if dog.neutered is None else str(dog.neutered).lower(),
        "status": dog.status,
        "description": dog.description or "",
        "shelter_id": str(dog.shelter_id) if dog.shelter_id else "",
        "assigned_volunteer_id": (
            str(dog.assigned_volunteer_id) if dog.assigned_volunteer_id else ""
        ),
        "owner_id": str(dog.owner_id) if dog.owner_id else "",
        "birthday": dog.birthday.isoformat() if dog.birthday else "",
        "status_at": dog.status_at.isoformat() if dog.status_at else "",
        "breed": dog.breed or "",
        "mixed": "" if dog.mixed is None else str(dog.mixed).lower(),
    }


def _dog_detail_response(
    request: Request,
    session: SessionDep,
    user: CurrentUser,
    dog_id: uuid.UUID,
    *,
    error: str | None = None,
    status_code: int = 200,
    form: dict[str, str] | None = None,
) -> Any:
    try:
        context = dog_service.get_dog_edit_context(session, dog_id)
    except dog_service.DogNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return templates.TemplateResponse(
        request,
        "dog_detail.html",
        {
            "user": user,
            "dog": context.dog,
            "shelters": context.shelters,
            "owners": context.owners,
            "volunteers": context.volunteers,
            "created_by": context.created_by,
            "statuses": [item.value for item in DogStatus],
            "form": form or _dog_form_from_row(context.dog),
            "error": error,
        },
        status_code=status_code,
    )


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
                    "href": f"/dogs/{dog.id}",
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


@router.get("/dogs/{dog_id}")
def dog_detail(
    request: Request,
    session: SessionDep,
    user: CurrentUser,
    dog_id: uuid.UUID,
) -> Any:
    return _dog_detail_response(request, session, user, dog_id)


@router.post("/dogs/{dog_id}")
def dog_update(
    request: Request,
    session: SessionDep,
    user: CurrentUser,
    dog_id: uuid.UUID,
    name: str = Form(""),
    sex: str = Form(""),
    neutered: str = Form(""),
    status: str = Form(""),
    description: str = Form(""),
    shelter_id: str = Form(""),
    assigned_volunteer_id: str = Form(""),
    owner_id: str = Form(""),
    birthday: str = Form(""),
    status_at: str = Form(""),
    breed: str = Form(""),
    mixed: str = Form(""),
) -> Any:
    form = _form_values(
        name=name,
        sex=sex,
        neutered=neutered,
        status=status,
        description=description,
        shelter_id=shelter_id,
        assigned_volunteer_id=assigned_volunteer_id,
        owner_id=owner_id,
        birthday=birthday,
        status_at=status_at,
        breed=breed,
        mixed=mixed,
    )
    try:
        dog_service.update_dog(
            session,
            dog_id,
            name=name,
            sex=sex or None,
            neutered=_optional_bool(neutered),
            status=DogStatus(status),
            description=description or None,
            shelter_id=_optional_uuid(shelter_id),
            assigned_volunteer_id=_optional_uuid(assigned_volunteer_id),
            owner_id=_optional_uuid(owner_id),
            birthday=_optional_date(birthday),
            status_at=_optional_date(status_at),
            breed=breed or None,
            mixed=_optional_bool(mixed),
        )
    except dog_service.DogNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (
        ValueError,
        dog_service.DogUpdateError,
        DomainValueValidationError,
    ) as exc:
        session.rollback()
        return _dog_detail_response(
            request,
            session,
            user,
            dog_id,
            error=str(exc),
            status_code=400,
            form=form,
        )
    return RedirectResponse(f"/dogs/{dog_id}", status_code=303)
