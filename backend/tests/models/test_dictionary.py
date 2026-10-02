import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.core.config import settings
from app.models import Dictionary, User


def test_dictionaries_table_columns(db: Session) -> None:
    inspector = inspect(db.get_bind())
    columns = {column["name"] for column in inspector.get_columns("dictionaries")}
    assert columns == {
        "key",
        "value",
        "created_at",
        "created_by",
        "updated_at",
        "updated_by",
    }
    pk = inspector.get_pk_constraint("dictionaries")
    assert pk["constrained_columns"] == ["key"]
    foreign_keys = inspector.get_foreign_keys("dictionaries")
    assert {tuple(item["constrained_columns"]) for item in foreign_keys} == {
        ("created_by",),
        ("updated_by",),
    }
    assert all(item["referred_table"] == "users" for item in foreign_keys)


def test_dictionary_persists_json_and_audit(db: Session) -> None:
    user = db.exec(select(User).where(User.email == settings.FIRST_SUPERUSER)).first()
    assert user
    row = Dictionary(
        key="breeds",
        value={"items": ["labrador"]},
        created_by=user.id,
        updated_by=user.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    assert row.key == "breeds"
    assert row.value == {"items": ["labrador"]}
    assert row.created_by == user.id
    assert row.updated_by == user.id
    assert row.created_at is not None
    assert row.updated_at is not None


def test_dictionary_key_is_unique(db: Session) -> None:
    user = db.exec(select(User).where(User.email == settings.FIRST_SUPERUSER)).first()
    assert user
    db.add(
        Dictionary(
            key="colors",
            value=["black"],
            created_by=user.id,
            updated_by=user.id,
        )
    )
    db.commit()
    db.add(
        Dictionary(
            key="colors",
            value=["white"],
            created_by=user.id,
            updated_by=user.id,
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
