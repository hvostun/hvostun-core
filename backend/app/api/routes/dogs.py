import uuid
from typing import Any

from fastapi import APIRouter
from sqlmodel import col, func, select

from app.api.deps import CurrentUser, SessionDep
from app.models import Dog, DogPublic, DogsPublic

router = APIRouter(prefix="/dogs", tags=["dogs"])


@router.get("/", response_model=DogsPublic)
def read_dogs(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 50,
    name: str | None = None,
    status: str | None = None,
    shelter_id: uuid.UUID | None = None,
    owner_id: uuid.UUID | None = None,
) -> Any:
    _ = current_user
    filters = []
    if name:
        filters.append(col(Dog.name).ilike(f"%{name}%"))
    if status:
        filters.append(Dog.status == status)
    if shelter_id:
        filters.append(Dog.shelter_id == shelter_id)
    if owner_id:
        filters.append(Dog.owner_id == owner_id)

    count_statement = select(func.count()).select_from(Dog)
    statement = select(Dog)
    if filters:
        count_statement = count_statement.where(*filters)
        statement = statement.where(*filters)

    count = session.exec(count_statement).one()
    dogs = session.exec(
        statement.order_by(col(Dog.created_at).desc()).offset(skip).limit(limit)
    ).all()
    return DogsPublic(
        data=[DogPublic.model_validate(dog) for dog in dogs],
        count=count,
    )
