from fastapi import APIRouter

from app.admin.routes import auth, dogs, management, sessions, surveys

router = APIRouter(tags=["admin-ui"])
router.include_router(auth.router)
router.include_router(dogs.router)
router.include_router(surveys.router)
router.include_router(sessions.router)
router.include_router(management.router)
