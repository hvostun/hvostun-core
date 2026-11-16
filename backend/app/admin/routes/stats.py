from typing import Any

from fastapi import APIRouter, Request

from app.admin.deps import SessionDep, StatsViewer
from app.admin.templating import templates
from app.services import stats as stats_service
from app.services.stats import ExpertStatsRow

router = APIRouter()


def _active_only(request: Request) -> bool:
    # Hidden input sends 0; a checked box appends 1. The last value wins.
    values = request.query_params.getlist("active")
    if not values:
        return True
    return values[-1] != "0"


def _format_metric(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:.1f}".replace(".", ",")


def _row_cells(row: ExpertStatsRow) -> dict[str, str | int]:
    return {
        "expert": row.label,
        "surveys": row.surveys,
        "average": _format_metric(row.average),
        "median": _format_metric(row.median),
    }


@router.get("/stats")
def stats_page(request: Request, session: SessionDep, user: StatsViewer) -> Any:
    active_only = _active_only(request)
    return templates.TemplateResponse(
        request,
        "stats.html",
        {
            "user": user,
            "active_only": active_only,
            "totals": stats_service.expert_totals(session),
            "rows": [
                _row_cells(row)
                for row in stats_service.expert_rows(session, active_only=active_only)
            ],
        },
    )
