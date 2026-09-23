from typing import Any

from fastapi import APIRouter, Depends
from sqlmodel import col, func, select

from app.api.deps import SessionDep, get_current_active_superuser
from app.models import Owner, OwnerPublic, OwnersPublic

router = APIRouter(prefix="/owners", tags=["owners"])


@router.get(
    "/",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=OwnersPublic,
)
def read_owners(
    session: SessionDep,
    skip: int = 0,
    limit: int = 50,
    name: str | None = None,
    email: str | None = None,
    phone: str | None = None,
) -> Any:
    filters = []
    if name:
        filters.append(col(Owner.name).ilike(f"%{name}%"))
    if email:
        filters.append(col(Owner.email).ilike(f"%{email}%"))
    if phone:
        filters.append(col(Owner.phone).ilike(f"%{phone}%"))

    count_statement = select(func.count()).select_from(Owner)
    statement = select(Owner)
    if filters:
        count_statement = count_statement.where(*filters)
        statement = statement.where(*filters)

    count = session.exec(count_statement).one()
    owners = session.exec(
        statement.order_by(col(Owner.created_at).desc()).offset(skip).limit(limit)
    ).all()
    return OwnersPublic(
        data=[OwnerPublic.model_validate(owner) for owner in owners],
        count=count,
    )
