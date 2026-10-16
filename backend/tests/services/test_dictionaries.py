import pytest
from sqlmodel import Session, select

from app.core.config import settings
from app.models import Dictionary, User
from app.services.dictionaries import (
    DEFAULT_GROUP_COLOR,
    DOGS_SEX_KEY,
    DOGS_STATUS_KEY,
    GIGACHAT_MODELS_KEY,
    SURVEYS_QUESTIONS_GROUP_KEY,
    DictionaryConflictError,
    DictionaryNotFoundError,
    create_dictionary,
    get_dictionary,
    gigachat_model_label,
    group_color,
    group_name,
    label_for,
    list_gigachat_models,
    normalize_key,
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


def test_group_entry_reads_name_and_color(db: Session) -> None:
    user = db.exec(select(User).where(User.email == settings.FIRST_SUPERUSER)).first()
    assert user
    groups = {
        "Energy": {"name": "Уровень энергии", "color": "var(--bs-teal)"},
        "Health": {"color": "var(--bs-red)"},
    }
    row = db.get(Dictionary, SURVEYS_QUESTIONS_GROUP_KEY)
    if row is None:
        db.add(
            Dictionary(
                key=SURVEYS_QUESTIONS_GROUP_KEY,
                value=groups,
                created_by=user.id,
                updated_by=user.id,
            )
        )
    else:
        row.value = groups
        db.add(row)
    db.commit()
    assert group_name(db, "Energy") == "Уровень энергии"
    assert group_color(db, "Energy") == "var(--bs-teal)"
    assert group_name(db, "Health") == "Health"
    assert group_color(db, "Health") == "var(--bs-red)"
    assert group_name(db, "Missing") == "Missing"
    assert group_color(db, "Missing") == DEFAULT_GROUP_COLOR
    assert group_name(db, None) == ""
    assert group_color(db, None) == DEFAULT_GROUP_COLOR


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


def test_create_dictionary_writes_row(db: Session) -> None:
    user = db.exec(select(User).where(User.email == settings.FIRST_SUPERUSER)).first()
    assert user
    key = f"ns::{random_lower_string()}"
    row = create_dictionary(db, key=f"  {key}  ", value=["a", "b"], created_by=user)
    assert row.key == key
    assert row.value == ["a", "b"]
    assert row.created_by == user.id
    assert row.updated_by == user.id
    assert db.get(Dictionary, key) is not None


def test_create_dictionary_rejects_duplicate(db: Session) -> None:
    user = db.exec(select(User).where(User.email == settings.FIRST_SUPERUSER)).first()
    assert user
    key = f"ns::{random_lower_string()}"
    create_dictionary(db, key=key, value={}, created_by=user)
    with pytest.raises(DictionaryConflictError, match="уже есть"):
        create_dictionary(db, key=key, value={"x": 1}, created_by=user)


def test_normalize_key_rejects_invalid() -> None:
    assert normalize_key(" dogs::sex ") == "dogs::sex"
    with pytest.raises(ValueError, match="обязателен"):
        normalize_key("   ")
    with pytest.raises(ValueError, match="Ключ"):
        normalize_key("bad key")


def test_get_dictionary_missing_raises(db: Session) -> None:
    with pytest.raises(DictionaryNotFoundError):
        get_dictionary(db, f"missing-{random_lower_string()}")


def test_list_gigachat_models_from_list_dict_and_default(db: Session) -> None:
    user = db.exec(select(User).where(User.email == settings.FIRST_SUPERUSER)).first()
    assert user
    assert GIGACHAT_MODELS_KEY == "gigachat::models"
    # No dictionary row → only env default.
    assert list_gigachat_models(db) == [settings.GIGACHAT_MODEL]

    db.add(
        Dictionary(
            key=GIGACHAT_MODELS_KEY,
            value=["ExtraModel-A", "ExtraModel-B"],
            created_by=user.id,
            updated_by=user.id,
        )
    )
    db.commit()
    models = list_gigachat_models(db)
    assert models[0] == settings.GIGACHAT_MODEL
    assert "ExtraModel-A" in models
    assert "ExtraModel-B" in models

    row = db.get(Dictionary, GIGACHAT_MODELS_KEY)
    assert row is not None
    row.value = {"ExtraModel-B": "B", "ExtraModel-A": "A"}
    db.add(row)
    db.commit()
    models = list_gigachat_models(db)
    assert models[0] == settings.GIGACHAT_MODEL
    assert gigachat_model_label(db, "ExtraModel-B") == "B"
    assert gigachat_model_label(db, "unknown-model") == "unknown-model"
