from fastapi import APIRouter, Depends

from app.admin.deps import enforce_csrf, forbid_auditor_writes
from app.admin.routes import (
    auth,
    dictionaries,
    dogs,
    management,
    scales,
    sessions,
    stats,
    surveys,
)

router = APIRouter(
    tags=["admin-ui"],
    dependencies=[Depends(enforce_csrf), Depends(forbid_auditor_writes)],
)
router.include_router(auth.router)
router.include_router(dogs.router)
router.include_router(surveys.router)
router.include_router(scales.router)
router.include_router(dictionaries.router)
router.include_router(sessions.router)
router.include_router(stats.router)
router.include_router(management.router)
