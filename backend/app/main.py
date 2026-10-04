from pathlib import Path

import sentry_sdk
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.admin.deps import CsrfCookieMiddleware
from app.admin.router import router as admin_router
from app.core.config import settings

if settings.SENTRY_DSN and settings.FASTAPI_ENV != "development":
    sentry_sdk.init(dsn=str(settings.SENTRY_DSN), enable_tracing=True)

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=None,
    docs_url=None,
    redoc_url=None,
)

app.add_middleware(CsrfCookieMiddleware)
app.include_router(admin_router)
app.mount(
    "/static",
    StaticFiles(directory=Path(__file__).resolve().parent / "admin" / "static"),
    name="static",
)


@app.get("/health", include_in_schema=False)
async def health() -> dict[str, str]:
    return {"status": "ok"}
