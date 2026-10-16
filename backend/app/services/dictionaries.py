import re
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from app.core.config import settings
from app.models import Dictionary, User

_KEY_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.:-]{0,254}$")

DOGS_SEX_KEY = "dogs::sex"
DOGS_STATUS_KEY = "dogs::status"
SURVEYS_QUESTIONS_GROUP_KEY = "surveys_questions::group"
SURVEYS_QUESTIONS_CONSTS_KEY = "surveys_questions::consts"
# Ordered list[str] of model ids, or dict[str, label] (keys = ids, order preserved).
GIGACHAT_MODELS_KEY = "gigachat::models"
DEFAULT_GROUP_COLOR = "var(--bs-blue)"


def get_value(session: Session, key: str) -> Any | None:
    row = session.get(Dictionary, key)
    return None if row is None else row.value


def label_for(session: Session, key: str, code: str | None) -> str:
    if not code:
        return ""
    value = get_value(session, key)
    if not isinstance(value, dict) or code not in value:
        return ""
    label = value[code]
    return "" if label is None else str(label)


def list_gigachat_models(session: Session) -> list[str]:
    """Model ids for GigaChat calls: dictionary first, else env default.

    Dictionary ``gigachat::models`` value:
    - ``["GigaChat-2-Max", "GigaChat"]`` — ordered ids;
    - ``{"GigaChat-2-Max": "Max", "GigaChat": "Lite"}`` — ids as keys.
    ``GIGACHAT_MODEL`` is always included (prepended if missing from the list).
    """
    value = get_value(session, GIGACHAT_MODELS_KEY)
    models: list[str] = []
    if isinstance(value, list):
        models = [str(item).strip() for item in value if str(item).strip()]
    elif isinstance(value, dict):
        models = [str(key).strip() for key in value if str(key).strip()]
    default = settings.GIGACHAT_MODEL.strip()
    if default and default not in models:
        models = [default, *models]
    return models


def gigachat_model_label(session: Session, model_id: str) -> str:
    value = get_value(session, GIGACHAT_MODELS_KEY)
    if isinstance(value, dict):
        label = value.get(model_id)
        if isinstance(label, str) and label.strip():
            return label.strip()
    return model_id


def _group_entry(session: Session, code: str) -> dict[str, Any] | None:
    value = get_value(session, SURVEYS_QUESTIONS_GROUP_KEY)
    if not isinstance(value, dict):
        return None
    entry = value.get(code)
    return entry if isinstance(entry, dict) else None


def group_name(session: Session, code: str | None) -> str:
    text = "" if code is None else str(code)
    if not text:
        return ""
    entry = _group_entry(session, text)
    if entry is None:
        return text
    name = entry.get("name")
    if isinstance(name, str) and name:
        return name
    return text


def group_color(session: Session, code: str | None) -> str:
    text = "" if code is None else str(code)
    entry = _group_entry(session, text) if text else None
    if entry is None:
        return DEFAULT_GROUP_COLOR
    color = entry.get("color")
    if isinstance(color, str) and color:
        return color
    return DEFAULT_GROUP_COLOR


class DictionaryNotFoundError(LookupError):
    pass


class DictionaryConflictError(ValueError):
    pass


def normalize_key(key: str) -> str:
    text = key.strip()
    if not text:
        raise ValueError("Ключ обязателен")
    if not _KEY_RE.fullmatch(text):
        raise ValueError(
            "Ключ: латиница, цифры, «_», «.», «:», «-»; начинается с буквы или цифры"
        )
    return text


def get_dictionary(session: Session, key: str) -> Dictionary:
    row = session.get(Dictionary, key)
    if row is None:
        raise DictionaryNotFoundError("Dictionary not found")
    return row


def create_dictionary(
    session: Session,
    *,
    key: str,
    value: Any,
    created_by: User,
) -> Dictionary:
    normalized = normalize_key(key)
    if session.get(Dictionary, normalized) is not None:
        raise DictionaryConflictError("Такой ключ уже есть")
    row = Dictionary(
        key=normalized,
        value=value,
        created_by=created_by.id,
        updated_by=created_by.id,
    )
    session.add(row)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise DictionaryConflictError("Такой ключ уже есть") from exc
    session.refresh(row)
    return row


def update_dictionary(
    session: Session,
    key: str,
    *,
    value: Any,
    updated_by: User,
) -> Dictionary:
    row = get_dictionary(session, key)
    row.value = value
    row.updated_by = updated_by.id
    session.add(row)
    session.commit()
    session.refresh(row)
    return row
