import uuid
from datetime import date

import pytest
from sqlmodel import Session

from app.models import Dog, Shelter
from app.services.dogs import DogUpdateError, update_dog


def test_update_dog_rejects_missing_shelter(db: Session) -> None:
    dog = Dog(name="No Shelter", status="unknown")
    db.add(dog)
    db.commit()
    db.refresh(dog)
    with pytest.raises(DogUpdateError, match="Приют не найден"):
        update_dog(
            db,
            dog.id,
            name="No Shelter",
            sex=None,
            neutered=None,
            status=dog.status,
            description=None,
            shelter_id=uuid.uuid4(),
            assigned_volunteer_id=None,
            owner_id=None,
            birthday=None,
            status_at=None,
            breed=None,
            mixed=None,
        )


def test_update_dog_sets_optional_fields(db: Session) -> None:
    shelter = Shelter(name="Сервисный приют")
    db.add(shelter)
    db.commit()
    db.refresh(shelter)
    dog = Dog(name="Service Dog", status="unknown")
    db.add(dog)
    db.commit()
    db.refresh(dog)
    updated = update_dog(
        db,
        dog.id,
        name="Service Dog",
        sex="female",
        neutered=False,
        status=dog.status,
        description=None,
        shelter_id=shelter.id,
        assigned_volunteer_id=None,
        owner_id=None,
        birthday=date(2025, 1, 1),
        status_at=date(2026, 2, 2),
        breed=None,
        mixed=True,
    )
    assert updated.shelter_id == shelter.id
    assert updated.birthday == date(2025, 1, 1)
    assert updated.status_at == date(2026, 2, 2)
    assert updated.mixed is True
