from typing import Any

from sqlmodel import Session

from app.models import Dictionary, User

DOGS_SEX_KEY = "dogs::sex"
DOGS_STATUS_KEY = "dogs::status"
SURVEYS_QUESTIONS_GROUP_KEY = "surveys_questions::group"
SURVEYS_QUESTIONS_CONSTS_KEY = "surveys_questions::consts"
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


def get_dictionary(session: Session, key: str) -> Dictionary:
    row = session.get(Dictionary, key)
    if row is None:
        raise DictionaryNotFoundError("Dictionary not found")
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
