"""Telegram Bot API client for the daily markup report."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(15.0)


class TelegramNotConfigured(RuntimeError):
    pass


def send_message(text: str) -> list[str]:
    """Post ``text`` to every configured chat. Returns chat ids that failed.

    One failed chat does not stop the others. The exception text from httpx
    is not logged: it includes the request URL, and that URL contains the bot token.
    """
    token = settings.TELEGRAM_BOT_TOKEN
    chat_ids = settings.telegram_chat_ids
    if not token or not chat_ids:
        raise TelegramNotConfigured("Telegram не настроен")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    failed: list[str] = []
    with httpx.Client(timeout=_TIMEOUT) as client:
        for chat_id in chat_ids:
            if not _post(client, url, chat_id, text):
                failed.append(chat_id)
    return failed


def _post(client: httpx.Client, url: str, chat_id: str, text: str) -> bool:
    try:
        response = client.post(
            url,
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
        )
    except httpx.HTTPError as exc:
        logger.warning(
            "Telegram transport error chat=%s: %s", chat_id, type(exc).__name__
        )
        return False
    if response.status_code >= 400:
        logger.warning("Telegram status=%s chat=%s", response.status_code, chat_id)
        return False
    try:
        payload: Any = response.json()
    except ValueError:
        logger.warning("Telegram invalid JSON chat=%s", chat_id)
        return False
    if not isinstance(payload, dict) or payload.get("ok") is not True:
        logger.warning("Telegram refused chat=%s", chat_id)
        return False
    return True
