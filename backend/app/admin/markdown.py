"""Render model answers as HTML. Markdown in, sanitized HTML out."""

import markdown as markdown_lib # type: ignore[import-untyped]

import nh3
from markupsafe import Markup

_TAGS = {
    "p",
    "br",
    "hr",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "ul",
    "ol",
    "li",
    "strong",
    "em",
    "code",
    "pre",
    "blockquote",
    "a",
    "table",
    "thead",
    "tbody",
    "tr",
    "th",
    "td",
}
_ATTRIBUTES = {
    "a": {"href"},
    "th": {"align"},
    "td": {"align"},
    "ol": {"start"},
    "code": {"class"},
}


def render_markdown(text: str) -> str:
    raw = markdown_lib.markdown(text, extensions=["extra", "sane_lists"])
    return nh3.clean(
        raw,
        tags=_TAGS,
        attributes=_ATTRIBUTES,
        url_schemes={"http", "https", "mailto"},
        link_rel="noopener noreferrer nofollow",
    )


def markdown_filter(value: object) -> Markup:
    if not isinstance(value, str) or not value.strip():
        return Markup("")
    return Markup(render_markdown(value))
