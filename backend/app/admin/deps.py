import hmac
import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from starlette.datastructures import MutableHeaders
from starlette.responses import Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core import security
from app.core.config import settings
from app.core.deps import SessionDep as SessionDep
from app.models import User, UserGroup

COOKIE_NAME = "admin_access_token"
CSRF_COOKIE_NAME = "admin_csrf"


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


def is_admin(user: User) -> bool:
    return user.is_superuser or user.group == UserGroup.ADMIN


def get_current_admin(current_user: CurrentUser) -> User:
    if not is_admin(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return current_user


AdminUser = Annotated[User, Depends(get_current_admin)]


def get_current_superuser(current_user: CurrentUser) -> User:
    if not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return current_user


SuperUser = Annotated[User, Depends(get_current_superuser)]


def _csrf_cookie_header(token: str) -> str:
    response = Response()
    response.set_cookie(
        CSRF_COOKIE_NAME,
        token,
        httponly=True,
        samesite="strict",
        secure=settings.is_deployed,
        path="/",
    )
    for key, value in response.raw_headers:
        if key.lower() == b"set-cookie":
            return value.decode("latin-1")
    raise RuntimeError("CSRF cookie header was not set")


def csrf_tokens_match(cookie: str | None, submitted: object) -> bool:
    if not cookie or not isinstance(submitted, str):
        return False
    if len(cookie) != len(submitted):
        return False
    return hmac.compare_digest(cookie, submitted)


class CsrfCookieMiddleware:
    """Issues the double-submit CSRF cookie without reading the request body."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request = Request(scope, receive)
        token = request.cookies.get(CSRF_COOKIE_NAME)
        if token:
            request.state.csrf_token = token
            await self.app(scope, receive, send)
            return
        token = secrets.token_urlsafe(32)
        request.state.csrf_token = token
        header = _csrf_cookie_header(token)

        async def send_with_cookie(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers.append("set-cookie", header)
            await send(message)

        await self.app(scope, receive, send_with_cookie)


async def enforce_csrf(request: Request) -> None:
    if request.method != "POST":
        return
    form = await request.form()
    if not csrf_tokens_match(
        request.cookies.get(CSRF_COOKIE_NAME), form.get("csrf_token")
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF check failed",
        )
