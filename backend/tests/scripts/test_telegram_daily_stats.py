from datetime import date, datetime, time
from zoneinfo import ZoneInfo

import httpx
import pytest
from sqlmodel import Session

from app import crud
from app.core.config import settings
from app.models import (
    Dog,
    Owner,
    Recommendation,
    SessionRecommendation,
    Survey,
    SurveySession,
    SurveyVersion,
    UserCreate,
    UserGroup,
)
from app.services import telegram
from app.services.stats import build_report, expert_totals, yesterday_bounds
from scripts.telegram_daily_stats import main, next_run
from tests.utils.utils import random_lower_string

_MOSCOW = ZoneInfo("Europe/Moscow")


def test_yesterday_bounds_are_moscow_calendar_day() -> None:
    since, until = yesterday_bounds(date(2026, 11, 16), _MOSCOW)
    assert since == datetime(2026, 11, 15, 0, 0, tzinfo=_MOSCOW)
    assert until == datetime(2026, 11, 16, 0, 0, tzinfo=_MOSCOW)


def test_next_run_before_and_after_eleven() -> None:
    at = time(11, 0)
    before = datetime(2026, 11, 16, 10, 30, tzinfo=_MOSCOW)
    after = datetime(2026, 11, 16, 11, 1, tzinfo=_MOSCOW)
    exact = datetime(2026, 11, 16, 11, 0, tzinfo=_MOSCOW)
    assert next_run(before, at) == datetime(2026, 11, 16, 11, 0, tzinfo=_MOSCOW)
    assert next_run(after, at) == datetime(2026, 11, 17, 11, 0, tzinfo=_MOSCOW)
    assert next_run(exact, at) == exact


def _assign(db: Session, when: datetime) -> None:
    user = crud.create_user(
        session=db,
        user_create=UserCreate(
            email=f"report-{random_lower_string()}@example.com",
            password=f"Stat1-{random_lower_string()[:8]}",
            group=UserGroup.MODERATOR,
        ),
    )
    owner = Owner(name=f"Владелец {random_lower_string()}")
    dog = Dog(name=f"Пёс {random_lower_string()}")
    survey = Survey(name="Отчёт", slug=f"report-{random_lower_string()}")
    db.add(owner)
    db.add(dog)
    db.add(survey)
    db.commit()
    db.refresh(dog)
    db.refresh(survey)
    version = SurveyVersion(survey_id=survey.id, version_num=1)
    db.add(version)
    db.commit()
    db.refresh(version)
    session_row = SurveySession(
        owner_id=owner.id,
        dog_id=dog.id,
        survey_version_id=version.id,
        status="draft",
    )
    recommendation = Recommendation(
        name="Рекомендация",
        slug=f"report-rec-{random_lower_string()}",
        text="Текст",
    )
    db.add(session_row)
    db.add(recommendation)
    db.commit()
    db.refresh(session_row)
    db.refresh(recommendation)
    db.add(
        SessionRecommendation(
            user_id=user.id,
            session_id=session_row.id,
            recomendation_id=recommendation.id,
            chart_number=0,
            weight=1.0,
            created_at=when,
        )
    )
    db.commit()


def test_build_report_counts_non_expert_inside_yesterday(db: Session) -> None:
    zone = _MOSCOW
    _assign(db, datetime(1998, 3, 1, 12, tzinfo=zone))
    _assign(db, datetime(1998, 3, 1, 18, tzinfo=zone))
    _assign(db, datetime(1998, 1, 15, 12, tzinfo=zone))
    report = build_report(db, date(1998, 3, 2), zone)
    total = expert_totals(db)
    assert report == (
        "Статистика разметки за 01.03.1998\n"
        "Анкет обработано: 2\n"
        "Рекомендаций дано: 2\n"
        "\n"
        "Всего\n"
        f"Анкет обработано: {total.surveys}\n"
        f"Рекомендаций дано: {total.recommendations}"
    )


def test_send_message_posts_each_chat_and_keeps_going(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    posts: list[dict[str, str]] = []

    class FakeResponse:
        def __init__(self, ok: bool, status: int) -> None:
            self.status_code = status
            self._ok = ok

        def json(self) -> dict[str, bool]:
            return {"ok": self._ok}

    class FakeClient:
        def __init__(self, *args: object, timeout: object = None) -> None:
            assert timeout is not None

        def __enter__(self) -> FakeClient:
            return self

        def __exit__(self, *args: object) -> bool:
            return False

        def post(self, url: str, json: dict[str, str]) -> FakeResponse:
            assert url.startswith("https://api.telegram.org/botsecret-token/")
            posts.append(json)
            if json["chat_id"] == "@chan":
                raise httpx.ConnectError("down")
            return FakeResponse(ok=True, status=200)

    monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", "secret-token")
    monkeypatch.setattr(settings, "TELEGRAM_CHAT_IDS", " @chan, -1001 ,")
    monkeypatch.setattr(telegram.httpx, "Client", FakeClient)

    failed = telegram.send_message("hello")

    assert failed == ["@chan"]
    assert posts == [
        {"chat_id": "@chan", "text": "hello", "parse_mode": "HTML"},
        {"chat_id": "-1001", "text": "hello", "parse_mode": "HTML"},
    ]


def test_once_returns_2_when_telegram_is_not_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", None)
    monkeypatch.setattr(settings, "TELEGRAM_CHAT_IDS", None)
    assert main(["--once"]) == 2


def test_once_sends_the_report(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[str] = []
    monkeypatch.setattr(settings, "TELEGRAM_BOT_TOKEN", "secret-token")
    monkeypatch.setattr(settings, "TELEGRAM_CHAT_IDS", "@chan")

    def _send(text: str) -> list[str]:
        sent.append(text)
        return []

    monkeypatch.setattr(
        "scripts.telegram_daily_stats.telegram_service.send_message", _send
    )
    assert main(["--once"]) == 0
    assert sent
    assert sent[0].startswith("Статистика разметки за ")
    assert "Всего" in sent[0]
