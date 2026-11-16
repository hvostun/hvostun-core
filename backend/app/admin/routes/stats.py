import logging
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from app.admin.deps import SessionDep, StatsViewer
from app.admin.templating import templates
from app.core.config import settings
from app.services import stats as stats_service
from app.services.stats import ExpertStatsRow
from app.services.telegram import TelegramNotConfigured, send_message

logger = logging.getLogger(__name__)

router = APIRouter()

_TELEGRAM_OK = {"sent": "Статистика отправлена в канал"}
_TELEGRAM_ERR = {
    "missing": "Telegram не настроен: задайте TELEGRAM_BOT_TOKEN и TELEGRAM_CHAT_IDS",
    "failed": "Не удалось отправить статистику в канал",
    "timezone": "Неизвестная таймзона отчёта",
}


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


def _stats_context(
    request: Request, session: SessionDep, user: StatsViewer
) -> dict[str, Any]:
    active_only = _active_only(request)
    code = request.query_params.get("telegram")
    return {
        "user": user,
        "active_only": active_only,
        "notice": _TELEGRAM_OK.get(code or ""),
        "error": _TELEGRAM_ERR.get(code or ""),
        "totals": stats_service.expert_totals(session),
        "rows": [
            _row_cells(row)
            for row in stats_service.expert_rows(session, active_only=active_only)
        ],
    }


@router.get("/stats")
def stats_page(request: Request, session: SessionDep, user: StatsViewer) -> Any:
    return templates.TemplateResponse(
        request,
        "stats.html",
        _stats_context(request, session, user),
    )


@router.post("/stats/telegram")
def send_stats_to_telegram(session: SessionDep, _user: StatsViewer) -> RedirectResponse:
    """Send the daily report now. Same text as the 11:00 scheduler."""
    try:
        zone = ZoneInfo(settings.DAILY_STATS_TZ)
    except ZoneInfoNotFoundError:
        logger.error("Неизвестная таймзона DAILY_STATS_TZ=%s", settings.DAILY_STATS_TZ)
        return RedirectResponse("/stats?telegram=timezone", status_code=303)
    if not settings.telegram_enabled:
        return RedirectResponse("/stats?telegram=missing", status_code=303)
    text = stats_service.build_report(session, datetime.now(zone).date(), zone)
    try:
        failed = send_message(text)
    except TelegramNotConfigured:
        return RedirectResponse("/stats?telegram=missing", status_code=303)
    except Exception:
        logger.exception("Не удалось отправить статистику")
        return RedirectResponse("/stats?telegram=failed", status_code=303)
    if failed:
        logger.error("Не отправлено в: %s", ", ".join(failed))
        return RedirectResponse("/stats?telegram=failed", status_code=303)
    return RedirectResponse("/stats?telegram=sent", status_code=303)
