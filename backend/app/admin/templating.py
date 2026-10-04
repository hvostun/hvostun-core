from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from fastapi import Request
from fastapi.templating import Jinja2Templates

from app.models import User
from app.pagination import DEFAULT_PAGE_SIZE, page_count


def _template_context(request: Request) -> dict[str, Any]:
    return {"csrf_token": getattr(request.state, "csrf_token", "")}


templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parent / "templates"),
    context_processors=[_template_context],
)
PAGE_SIZE = DEFAULT_PAGE_SIZE


def cell(value: object) -> str:
    return "" if value is None else str(value)


def filter_qs(values: dict[str, str]) -> str:
    return urlencode({key: value for key, value in values.items() if value})


def list_context(
    *,
    request: Request,
    user: User,
    title: str,
    columns: list[dict[str, str]],
    rows: list[dict[str, Any]],
    count: int,
    page: int,
    filters: Sequence[Mapping[str, Any]],
    filter_values: dict[str, str],
    create_href: str | None = None,
    create_label: str | None = None,
) -> dict[str, Any]:
    return {
        "request": request,
        "user": user,
        "title": title,
        "columns": columns,
        "rows": rows,
        "count": count,
        "page": page,
        "pages": page_count(count, PAGE_SIZE),
        "filters": filters,
        "filter_qs": filter_qs(filter_values),
        "create_href": create_href,
        "create_label": create_label,
    }
