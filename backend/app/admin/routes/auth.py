from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from app import crud
from app.admin.deps import COOKIE_NAME, CurrentUser, OptionalUser, SessionDep
from app.admin.templating import templates
from app.core import security
from app.core.config import settings

router = APIRouter()


@router.get("/login")
def login_page(request: Request, user: OptionalUser) -> Any:
    if user is not None:
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(
        request, "login.html", {"user": None, "error": None, "email": ""}
    )


@router.post("/login")
def login_submit(
    request: Request,
    session: SessionDep,
    email: str = Form(),
    password: str = Form(),
) -> Any:
    user = crud.authenticate(session=session, email=email, password=password)
    if user is None or not user.is_active:
        return templates.TemplateResponse(
            request,
            "login.html",
            {
                "user": None,
                "error": "Неверный email или пароль",
                "email": email,
            },
            status_code=400,
        )
    token = security.create_access_token(
        user.id,
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    response = RedirectResponse("/", status_code=303)
    response.set_cookie(
        COOKIE_NAME,
        token,
        httponly=True,
        samesite="lax",
        secure=settings.is_deployed,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    return response


@router.post("/logout")
def logout() -> RedirectResponse:
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(COOKIE_NAME)
    return response


@router.get("/")
def home(request: Request, user: CurrentUser) -> Any:
    return templates.TemplateResponse(request, "home.html", {"user": user})
