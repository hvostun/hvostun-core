from time import sleep

from sqlmodel import Session

from app.models import Dog, DogChip, Shelter


def test_timestamp_mixin_fills_and_updates(db: Session) -> None:
    shelter = Shelter(name="ts-mixin-shelter")
    db.add(shelter)
    db.commit()
    db.refresh(shelter)

    assert shelter.created_at is not None
    assert shelter.updated_at is not None
    assert shelter.created_at.tzinfo is not None
    assert shelter.updated_at.tzinfo is not None
    created_at = shelter.created_at
    updated_at = shelter.updated_at

    sleep(0.02)
    shelter.description = "changed"
    db.add(shelter)
    db.commit()
    db.refresh(shelter)

    assert shelter.created_at == created_at
    assert shelter.updated_at > updated_at

    db.delete(shelter)
    db.commit()


def test_created_at_mixin_has_no_updated_at(db: Session) -> None:
    dog = Dog(name="ts-mixin-dog")
    db.add(dog)
    db.commit()
    db.refresh(dog)

    chip = DogChip(dog_id=dog.id, system="iso", code="ts-mixin-chip")
    db.add(chip)
    db.commit()
    db.refresh(chip)

    assert chip.created_at is not None
    assert chip.created_at.tzinfo is not None
    assert "updated_at" not in DogChip.__table__.c

    db.delete(chip)
    db.delete(dog)
    db.commit()
