from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from app.core import security
from app.core.deps import SessionDep as SessionDep
from app.models import User

COOKIE_NAME = "admin_access_token"


def _user_from_token(session: SessionDep, token: str) -> User | None:
    user_id = security.decode_access_token_subject(token)
    if user_id is None:
        return None
    user = session.get(User, user_id)
    if user is None or not user.is_active:
        return None
    return user


def get_optional_user(request: Request, session: SessionDep) -> User | None:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    return _user_from_token(session, token)


OptionalUser = Annotated[User | None, Depends(get_optional_user)]


def get_current_user(request: Request, session: SessionDep) -> User:
    user = get_optional_user(request, session)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/login"},
        )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_current_superuser(current_user: CurrentUser) -> User:
    if not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return current_user


SuperUser = Annotated[User, Depends(get_current_superuser)]
