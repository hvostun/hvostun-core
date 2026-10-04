import pytest
from sqlmodel import Session, select

from app.core.config import settings
from app.models import Dictionary, User
from app.services.dictionaries import (
    DOGS_SEX_KEY,
    DOGS_STATUS_KEY,
    SURVEYS_QUESTIONS_GROUP_KEY,
    DictionaryNotFoundError,
    get_dictionary,
    label_for,
    update_dictionary,
)
from tests.utils.utils import random_lower_string


def test_label_for_reads_json_map(db: Session) -> None:
    user = db.exec(select(User).where(User.email == settings.FIRST_SUPERUSER)).first()
    assert user
    key = f"dict-{random_lower_string()}"
    db.add(
        Dictionary(
            key=key,
            value={"female": "сука", "male": "кобель"},
            created_by=user.id,
            updated_by=user.id,
        )
    )
    db.commit()
    assert DOGS_SEX_KEY == "dogs::sex"
    assert DOGS_STATUS_KEY == "dogs::status"
    assert SURVEYS_QUESTIONS_GROUP_KEY == "surveys_questions::group"
    assert label_for(db, key, "female") == "сука"
    assert label_for(db, key, "male") == "кобель"
    assert label_for(db, key, "unknown") == ""
    assert label_for(db, key, None) == ""


def test_label_for_missing_key_is_empty(db: Session) -> None:
    assert label_for(db, f"missing-{random_lower_string()}", "female") == ""


def test_update_dictionary_writes_value_and_updated_by(db: Session) -> None:
    user = db.exec(select(User).where(User.email == settings.FIRST_SUPERUSER)).first()
    assert user
    key = f"dict-{random_lower_string()}"
    db.add(
        Dictionary(
            key=key,
            value={"a": 1},
            created_by=user.id,
            updated_by=user.id,
        )
    )
    db.commit()
    row = update_dictionary(db, key, value={"a": 2}, updated_by=user)
    assert row.value == {"a": 2}
    assert row.updated_by == user.id


def test_get_dictionary_missing_raises(db: Session) -> None:
    with pytest.raises(DictionaryNotFoundError):
        get_dictionary(db, f"missing-{random_lower_string()}")
