import math
from typing import Any

from sqlmodel import Session

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 100


def normalize_offset_limit(
    offset: int, limit: int, *, max_limit: int = MAX_PAGE_SIZE
) -> tuple[int, int]:
    return max(offset, 0), min(max(limit, 1), max_limit)


def page_window(page: int, page_size: int = DEFAULT_PAGE_SIZE) -> tuple[int, int, int]:
    normalized_page = max(page, 1)
    normalized_size = min(max(page_size, 1), MAX_PAGE_SIZE)
    return (
        (normalized_page - 1) * normalized_size,
        normalized_size,
        normalized_page,
    )


def page_count(count: int, page_size: int = DEFAULT_PAGE_SIZE) -> int:
    return max(1, math.ceil(count / page_size))


def execute_page(
    session: Session,
    count_statement: Any,
    statement: Any,
    *,
    offset: int,
    limit: int,
) -> tuple[list[Any], int]:
    count = session.exec(count_statement).one()
    rows = session.exec(statement.offset(offset).limit(limit)).all()
    return list(rows), count
