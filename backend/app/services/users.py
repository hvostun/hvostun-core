import uuid

from pydantic import ValidationError
from sqlmodel import Session

from app import crud
from app.models import User, UserCreate, UserGroup, UserUpdate

MIN_PASSWORD_LENGTH = 8


class UserNotFoundError(LookupError):
    pass


class UserFormError(ValueError):
    pass


def get_user(session: Session, user_id: uuid.UUID) -> User:
    user = session.get(User, user_id)
    if user is None:
        raise UserNotFoundError("User not found")
    return user


def _validation_message(exc: ValidationError) -> str:
    error = exc.errors()[0]
    location = error.get("loc") or ()
    message = str(error.get("msg") or "Некорректные данные")
    if location:
        return f"{location[-1]}: {message}"
    return message


def _parse_bool(raw: str, *, default: bool) -> bool:
    if raw == "true":
        return True
    if raw == "false":
        return False
    return default


def _optional_text(raw: str) -> str | None:
    text = raw.strip()
    return text or None


def create_admin_user(
    session: Session,
    *,
    email: str,
    password: str,
    full_name: str,
    group: str,
    phone: str,
    contact: str,
    is_active: str,
    is_superuser: str,
) -> User:
    if crud.get_user_by_email(session=session, email=email.strip()):
        raise UserFormError("Email уже занят")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise UserFormError(f"Пароль не короче {MIN_PASSWORD_LENGTH} символов")
    try:
        user_in = UserCreate(
            email=email.strip(),
            password=password,
            full_name=_optional_text(full_name),
            group=UserGroup(group),
            phone=_optional_text(phone),
            contact=_optional_text(contact),
            is_active=_parse_bool(is_active, default=True),
            is_superuser=_parse_bool(is_superuser, default=False),
        )
    except (ValueError, ValidationError) as exc:
        if isinstance(exc, ValidationError):
            raise UserFormError(_validation_message(exc)) from exc
        raise UserFormError(str(exc)) from exc
    return crud.create_user(session=session, user_create=user_in)


def update_admin_user(
    session: Session,
    *,
    user_id: uuid.UUID,
    current_user: User,
    email: str,
    password: str,
    full_name: str,
    group: str,
    phone: str,
    contact: str,
    is_active: str,
    is_superuser: str,
) -> User:
    user = get_user(session, user_id)
    next_active = _parse_bool(is_active, default=user.is_active)
    next_superuser = _parse_bool(is_superuser, default=user.is_superuser)
    if user.id == current_user.id and not next_active:
        raise UserFormError("Нельзя деактивировать свою учётную запись")
    if user.id == current_user.id and not next_superuser:
        raise UserFormError("Нельзя снять у себя флаг superuser")
    existing = crud.get_user_by_email(session=session, email=email.strip())
    if existing is not None and existing.id != user.id:
        raise UserFormError("Email уже занят")
    if password and len(password) < MIN_PASSWORD_LENGTH:
        raise UserFormError(f"Пароль не короче {MIN_PASSWORD_LENGTH} символов")
    try:
        payload: dict[str, object] = {
            "email": email.strip(),
            "full_name": _optional_text(full_name),
            "group": UserGroup(group),
            "phone": _optional_text(phone),
            "contact": _optional_text(contact),
            "is_active": next_active,
            "is_superuser": next_superuser,
        }
        if password:
            payload["password"] = password
        user_in = UserUpdate.model_validate(payload)
    except (ValueError, ValidationError) as exc:
        if isinstance(exc, ValidationError):
            raise UserFormError(_validation_message(exc)) from exc
        raise UserFormError(str(exc)) from exc
    return crud.update_user(session=session, db_user=user, user_in=user_in)
