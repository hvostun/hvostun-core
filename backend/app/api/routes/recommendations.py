from typing import Any

from fastapi import APIRouter, Depends
from sqlmodel import col, func, select

from app.api.deps import SessionDep, get_current_active_superuser
from app.models import Recommendation, RecommendationPublic, RecommendationsPublic
from app.pagination import execute_page, normalize_offset_limit

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.get(
    "/",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=RecommendationsPublic,
)
def read_recommendations(
    session: SessionDep,
    skip: int = 0,
    limit: int = 50,
    name: str | None = None,
    slug: str | None = None,
) -> Any:
    filters = []
    if name:
        filters.append(col(Recommendation.name).ilike(f"%{name}%"))
    if slug:
        filters.append(col(Recommendation.slug).ilike(f"%{slug}%"))

    count_statement = select(func.count()).select_from(Recommendation)
    statement = select(Recommendation)
    if filters:
        count_statement = count_statement.where(*filters)
        statement = statement.where(*filters)

    skip, limit = normalize_offset_limit(skip, limit)
    recommendations, count = execute_page(
        session,
        count_statement,
        statement.order_by(col(Recommendation.slug), col(Recommendation.created_at)),
        offset=skip,
        limit=limit,
    )
    return RecommendationsPublic(
        data=[RecommendationPublic.model_validate(item) for item in recommendations],
        count=count,
    )
