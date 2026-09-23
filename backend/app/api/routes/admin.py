from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(prefix="/admin", tags=["admin"])


class AdminContourStub(BaseModel):
    contour: str = Field(default="admin")
    status: str = Field(default="stub")


@router.get("/")
def admin_contour_stub() -> AdminContourStub:
    return AdminContourStub()
