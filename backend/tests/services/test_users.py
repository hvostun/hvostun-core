import pytest
from sqlmodel import Session, select

from app import crud
from app.core.config import settings
from app.models import User, UserGroup
from app.services.users import UserFormError, create_admin_user, update_admin_user
from tests.utils.utils import random_lower_string


def test_create_admin_user_rejects_short_password(db: Session) -> None:
    with pytest.raises(UserFormError, match="не короче"):
        create_admin_user(
            db,
            email=f"short-{random_lower_string()}@example.com",
            password="123",
            full_name="",
            group="expert",
            phone="",
            contact="",
            is_active="true",
            is_superuser="false",
        )


def test_update_admin_user_rejects_self_deactivate(db: Session) -> None:
    current = db.exec(
        select(User).where(User.email == settings.FIRST_SUPERUSER)
    ).first()
    assert current
    with pytest.raises(UserFormError, match="деактивировать"):
        update_admin_user(
            db,
            user_id=current.id,
            current_user=current,
            email=current.email,
            password="",
            full_name=current.full_name or "",
            group=current.group,
            phone=current.phone or "",
            contact=current.contact or "",
            is_active="false",
            is_superuser="true",
        )


def test_create_admin_user_writes_fields(db: Session) -> None:
    email = f"svc-{random_lower_string()}@example.com"
    user = create_admin_user(
        db,
        email=email,
        password="Secret12",
        full_name="Сервис",
        group="admin",
        phone="",
        contact="",
        is_active="true",
        is_superuser="true",
    )
    assert user.email == email
    assert user.group == UserGroup.ADMIN
    assert user.is_superuser is True
    assert crud.get_user_by_email(session=db, email=email) is not None
