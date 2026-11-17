import uuid
from datetime import timedelta

from app.core.security import (
    create_access_token,
    decode_access_token_subject,
)
from app.pagination import normalize_offset_limit, page_count, page_window


def test_pagination_bounds() -> None:
    assert normalize_offset_limit(-5, 0) == (0, 1)
    assert normalize_offset_limit(10, 1000) == (10, 100)
    assert page_window(0, 1000) == (0, 100, 1)
    assert page_window(3, 20) == (40, 20, 3)
    assert page_count(0, 50) == 1
    assert page_count(101, 50) == 3


def test_access_token_decoder() -> None:
    subject = uuid.uuid4()
    token = create_access_token(subject, timedelta(minutes=5))
    assert decode_access_token_subject(token) == subject
    assert decode_access_token_subject("invalid") is None
