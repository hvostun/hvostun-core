from fastapi import APIRouter, Depends

from app.admin.deps import enforce_csrf
from app.admin.routes import (
    auth,
    dictionaries,
    dogs,
    management,
    scales,
    sessions,
    surveys,
)

router = APIRouter(tags=["admin-ui"], dependencies=[Depends(enforce_csrf)])
router.include_router(auth.router)
router.include_router(dogs.router)
router.include_router(surveys.router)
router.include_router(scales.router)
router.include_router(dictionaries.router)
router.include_router(sessions.router)
router.include_router(management.router)
