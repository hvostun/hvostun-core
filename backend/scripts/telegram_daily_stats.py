#!/usr/bin/env python3
"""Send the daily markup report to Telegram channels.

The totals are ``expert_totals``: the same counts as the cards on ``/stats``,
including every author. Yesterday is the previous calendar day in
``DAILY_STATS_TZ``.

Run from the ``backend`` directory:

    uv run python scripts/telegram_daily_stats.py --dry-run
    uv run python scripts/telegram_daily_stats.py --once
    docker compose exec scheduler python scripts/telegram_daily_stats.py --once
"""

from __future__ import annotations

import argparse
import logging
import time
from datetime import datetime, timedelta
from datetime import time as dt_time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlmodel import Session

from app.core.config import settings
from app.core.db import engine
from app.services import telegram as telegram_service
from app.services.stats import build_report
from app.services.telegram import TelegramNotConfigured

logger = logging.getLogger(__name__)

# After a slot, step the clock so the next sleep lands on the following day
# even when the send finishes in the same second as DAILY_STATS_TIME.
_SLOT_GUARD_SECONDS = 1


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Отправить в Telegram статистику разметки за вчера",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Отправить сейчас и выйти",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Напечатать текст без отправки",
    )
    return parser.parse_args(argv)


def parse_stats_time(value: str) -> dt_time:
    hour_text, minute_text = value.split(":")
    return dt_time(hour=int(hour_text), minute=int(minute_text))


def next_run(now: datetime, at: dt_time) -> datetime:
    """Next ``at`` in ``now``'s timezone. An exact match is due immediately."""
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    candidate = now.replace(hour=at.hour, minute=at.minute, second=0, microsecond=0)
    if candidate < now:
        return candidate + timedelta(days=1)
    return candidate


def _render(zone: ZoneInfo) -> str:
    with Session(engine) as db:
        return build_report(db, datetime.now(zone).date(), zone)


def _deliver(text: str, *, dry_run: bool) -> int:
    if dry_run:
        print(text)
        return 0
    if not settings.telegram_enabled:
        logger.error("Telegram не настроен (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_IDS)")
        return 2
    try:
        failed = telegram_service.send_message(text)
    except TelegramNotConfigured:
        logger.error("Telegram не настроен (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_IDS)")
        return 2
    if failed:
        logger.error("Не отправлено в: %s", ", ".join(failed))
        return 1
    logger.info("Отправлено в %s", ", ".join(settings.telegram_chat_ids))
    return 0


def _schedule(zone: ZoneInfo, at: dt_time) -> int:
    while True:
        now = datetime.now(zone)
        run_at = next_run(now, at)
        delay = (run_at - now).total_seconds()
        logger.info("Следующая отправка %s", run_at.isoformat())
        if delay > 0:
            time.sleep(delay)
        try:
            code = _deliver(_render(zone), dry_run=False)
        except Exception:
            logger.exception("Не удалось отправить статистику")
            code = 1
        if code == 2:
            logger.error("Telegram не настроен, жду следующего запуска")
        time.sleep(_SLOT_GUARD_SECONDS)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    args = _parse_args(argv)
    try:
        zone = ZoneInfo(settings.DAILY_STATS_TZ)
    except ZoneInfoNotFoundError:
        logger.error("Неизвестная таймзона DAILY_STATS_TZ=%s", settings.DAILY_STATS_TZ)
        return 2
    try:
        at = parse_stats_time(settings.DAILY_STATS_TIME)
    except ValueError:
        logger.error("Некорректное DAILY_STATS_TIME=%s", settings.DAILY_STATS_TIME)
        return 2
    if args.once or args.dry_run:
        return _deliver(_render(zone), dry_run=args.dry_run)
    return _schedule(zone, at)


if __name__ == "__main__":
    raise SystemExit(main())
