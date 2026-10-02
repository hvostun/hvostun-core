from datetime import UTC, date, datetime
from types import SimpleNamespace

import pytest

from app.services.sessions import (
    UNANSWERED_FILTER,
    SessionRecommendationError,
    answer_progress,
    days_since_status,
    filter_session_answers,
    format_dog_age,
    parse_chart_number,
    parse_weight,
)


def test_days_since_status_counts_calendar_days() -> None:
    created = datetime(2026, 9, 25, 15, 0, tzinfo=UTC)
    assert days_since_status(date(2026, 9, 15), created) == 10
    assert days_since_status(None, created) is None
    assert days_since_status(date(2026, 9, 15), None) is None


def test_format_dog_age() -> None:
    assert format_dog_age(date(2024, 6, 25), date(2026, 9, 25)) == "2 г. 3 мес."
    assert format_dog_age(date(2026, 6, 25), date(2026, 9, 25)) == "3 мес."
    assert format_dog_age(None, date(2026, 9, 25)) == ""
    assert format_dog_age(date(2026, 10, 1), date(2026, 9, 25)) == ""


def test_parse_chart_and_weight() -> None:
    assert parse_chart_number("") == 0
    assert parse_chart_number("4") == 4
    assert parse_weight("") == 1.0
    assert parse_weight("0.4") == 0.4
    with pytest.raises(SessionRecommendationError, match="целым"):
        parse_chart_number("x")
    with pytest.raises(SessionRecommendationError, match="отрицательной"):
        parse_chart_number("-1")
    with pytest.raises(SessionRecommendationError, match="от 0 до 1"):
        parse_weight("1.5")


def test_filter_session_answers() -> None:
    first = SimpleNamespace(link=SimpleNamespace(group="Excitability"), display_value="3")
    second = SimpleNamespace(link=SimpleNamespace(group="Aggression"), display_value="")
    rows = [first, second]  # type: ignore[list-item]
    assert filter_session_answers(rows, category="Excitability") == [first]
    assert filter_session_answers(rows, answer="3") == [first]
    assert filter_session_answers(rows, answer=UNANSWERED_FILTER) == [second]
    assert filter_session_answers(rows, category="Aggression", answer="3") == []


def test_answer_progress_maps_scale_and_skips_missing() -> None:
    config = {"min_value": 0, "max_value": 4}
    bar = answer_progress({"value": 3}, config, "Excitability")
    assert bar["show_bar"] is True
    assert bar["percent"] == 75
    assert bar["color"] == "var(--bs-orange)"
    missing = answer_progress({"value": -999}, config, "Aggression")
    assert missing["show_bar"] is False
    assert missing["color"] == "var(--bs-red)"
    empty = answer_progress(None, config, "other")
    assert empty["show_bar"] is False
    zero = answer_progress({"value": 0}, {"min_value": -1, "max_value": 4}, "other")
    assert zero["show_bar"] is True
    assert zero["percent"] == 0
