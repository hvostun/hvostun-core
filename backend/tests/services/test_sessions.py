from datetime import UTC, date, datetime

import pytest

from app.services.sessions import (
    SessionRecommendationError,
    days_since_status,
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
