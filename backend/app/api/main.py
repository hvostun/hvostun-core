from fastapi import APIRouter

from app.api.routes import (
    admin,
    dogs,
    login,
    owners,
    private,
    recommendations,
    survey_sessions,
    surveys,
    users,
    utils,
)
from app.core.config import settings

api_router = APIRouter()
api_router.include_router(login.router)
api_router.include_router(users.router)
api_router.include_router(dogs.router)
api_router.include_router(owners.router)
api_router.include_router(surveys.router)
api_router.include_router(survey_sessions.router)
api_router.include_router(recommendations.router)
api_router.include_router(utils.router)
api_router.include_router(admin.router)


if settings.FASTAPI_ENV in {"development", "test"}:
    api_router.include_router(private.router)
