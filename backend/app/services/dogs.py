import uuid
from dataclasses import dataclass
from datetime import date

from sqlmodel import Session, col, select

from app.models import Dog, DogStatus, Owner, Shelter, User


class DogNotFoundError(LookupError):
    pass


class DogUpdateError(ValueError):
    pass


@dataclass(frozen=True)
class DogEditContext:
    dog: Dog
    shelters: list[Shelter]
    owners: list[Owner]
    volunteers: list[User]
    created_by: User | None


def get_dog(session: Session, dog_id: uuid.UUID) -> Dog:
    dog = session.get(Dog, dog_id)
    if dog is None:
        raise DogNotFoundError("Dog not found")
    return dog


def list_shelters(session: Session) -> list[Shelter]:
    return list(
        session.exec(select(Shelter).order_by(col(Shelter.name), col(Shelter.id)))
    )


def list_owners(session: Session) -> list[Owner]:
    return list(session.exec(select(Owner).order_by(col(Owner.name), col(Owner.id))))


def list_volunteers(session: Session) -> list[User]:
    return list(
        session.exec(
            select(User).where(User.is_active).order_by(col(User.email), col(User.id))
        )
    )


def get_dog_edit_context(session: Session, dog_id: uuid.UUID) -> DogEditContext:
    dog = get_dog(session, dog_id)
    created_by = session.get(User, dog.created_by_id) if dog.created_by_id else None
    return DogEditContext(
        dog=dog,
        shelters=list_shelters(session),
        owners=list_owners(session),
        volunteers=list_volunteers(session),
        created_by=created_by,
    )


def _require_fk(
    session: Session,
    model: type[Shelter] | type[Owner] | type[User],
    row_id: uuid.UUID | None,
    label: str,
) -> None:
    if row_id is None:
        return
    if session.get(model, row_id) is None:
        raise DogUpdateError(f"{label} не найден")


def update_dog(
    session: Session,
    dog_id: uuid.UUID,
    *,
    name: str,
    sex: str | None,
    neutered: bool | None,
    status: DogStatus,
    description: str | None,
    shelter_id: uuid.UUID | None,
    assigned_volunteer_id: uuid.UUID | None,
    owner_id: uuid.UUID | None,
    birthday: date | None,
    status_at: date | None,
    breed: str | None,
    mixed: bool | None,
) -> Dog:
    dog = get_dog(session, dog_id)
    if not name.strip():
        raise DogUpdateError("Имя обязательно")
    _require_fk(session, Shelter, shelter_id, "Приют")
    _require_fk(session, Owner, owner_id, "Владелец")
    _require_fk(session, User, assigned_volunteer_id, "Волонтёр")
    dog.name = name.strip()
    dog.sex = sex.strip() if sex and sex.strip() else None
    dog.neutered = neutered
    dog.status = status
    dog.description = (
        description.strip() if description and description.strip() else None
    )
    dog.shelter_id = shelter_id
    dog.assigned_volunteer_id = assigned_volunteer_id
    dog.owner_id = owner_id
    dog.birthday = birthday
    dog.status_at = status_at
    dog.breed = breed.strip() if breed and breed.strip() else None
    dog.mixed = mixed
    session.add(dog)
    session.commit()
    session.refresh(dog)
    return dog
