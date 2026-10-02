from typing import Any

from sqlmodel import Session

from app.models import Dictionary, User

DOGS_SEX_KEY = "dogs::sex"
DOGS_STATUS_KEY = "dogs::status"
SURVEYS_QUESTIONS_GROUP_KEY = "surveys_questions::group"


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
