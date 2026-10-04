from dataclasses import dataclass
from typing import Any

from sqlmodel import Session

from app.services import dictionaries as dictionary_service
from app.services.sessions import (
    DEFAULT_SCALE_MAX,
    DEFAULT_SCALE_MIN,
    SessionAnswer,
    answer_scalar,
    group_label,
)

CBARQ_SHORT_KEY = "c-barq-short-42"
OTHER_GROUP = "other"
# Sections at or above this score start open. Not a scoring threshold.
DOMAIN_OPEN_SCORE = 2


@dataclass(frozen=True)
class ScoringConsts:
    threshold: float | None
    reverse: frozenset[int]


@dataclass(frozen=True)
class ScoredPoint:
    order_num: int
    answer: SessionAnswer
    raw: int | None
    scored: int | None
    reversed: bool


@dataclass(frozen=True)
class DomainScore:
    key: str
    score: float | None
    answered: int
    total: int
    points: tuple[ScoredPoint, ...]


@dataclass(frozen=True)
class DomainScoring:
    domains: tuple[DomainScore, ...]
    unscored: tuple[SessionAnswer, ...]


def _integers(value: object) -> tuple[int, ...]:
    if not isinstance(value, list):
        return ()
    seen: set[int] = set()
    numbers: list[int] = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, int):
            continue
        if item in seen:
            continue
        seen.add(item)
        numbers.append(item)
    return tuple(numbers)


def parse_scoring_consts(value: object) -> ScoringConsts:
    if not isinstance(value, dict):
        return ScoringConsts(None, frozenset())
    block = value.get(CBARQ_SHORT_KEY)
    if not isinstance(block, dict):
        return ScoringConsts(None, frozenset())
    raw = block.get("domain_threshold")
    threshold = None
    if not isinstance(raw, bool) and isinstance(raw, int | float):
        threshold = float(raw)
    return ScoringConsts(threshold, frozenset(_integers(block.get("reverse"))))


def load_scoring_consts(session: Session) -> ScoringConsts:
    return parse_scoring_consts(
        dictionary_service.get_value(
            session, dictionary_service.SURVEYS_QUESTIONS_CONSTS_KEY
        )
    )


def _raw_score(answer: SessionAnswer) -> int | None:
    if answer.event is None:
        return None
    scalar = answer_scalar(answer.event.value)
    if isinstance(scalar, bool) or isinstance(scalar, str):
        return None
    if isinstance(scalar, float):
        if not scalar.is_integer():
            return None
        scalar = int(scalar)
    if not isinstance(scalar, int):
        return None
    if scalar < DEFAULT_SCALE_MIN or scalar > DEFAULT_SCALE_MAX:
        return None
    return scalar


def _point(answer: SessionAnswer, *, reverse: bool) -> ScoredPoint:
    raw = _raw_score(answer)
    scored = None if raw is None else (DEFAULT_SCALE_MAX - raw if reverse else raw)
    return ScoredPoint(
        order_num=answer.link.order_num,
        answer=answer,
        raw=raw,
        scored=scored,
        reversed=reverse,
    )


def _domain_score(
    key: str, answers: list[SessionAnswer], consts: ScoringConsts
) -> DomainScore:
    points = tuple(
        _point(answer, reverse=answer.link.order_num in consts.reverse)
        for answer in answers
    )
    counted = [point.scored for point in points if point.scored is not None]
    answered = len(counted)
    total = len(points)
    score: float | None = None
    if answered and total:
        ratio = answered / total
        if consts.threshold is None or ratio >= consts.threshold:
            score = round(sum(counted) / answered, 2)
    return DomainScore(
        key=key,
        score=score,
        answered=answered,
        total=total,
        points=points,
    )


def score_domains(answers: list[SessionAnswer], consts: ScoringConsts) -> DomainScoring:
    grouped: dict[str, list[SessionAnswer]] = {}
    order: list[str] = []
    unscored: list[SessionAnswer] = []
    for answer in answers:
        group = str(answer.link.group or OTHER_GROUP)
        if group == OTHER_GROUP:
            unscored.append(answer)
            continue
        if group not in grouped:
            order.append(group)
            grouped[group] = []
        grouped[group].append(answer)
    domains = tuple(_domain_score(key, grouped[key], consts) for key in order)
    return DomainScoring(domains=domains, unscored=tuple(unscored))


def score_session(
    session: Session, answers: list[SessionAnswer]
) -> DomainScoring | None:
    scoring = score_domains(answers, load_scoring_consts(session))
    if not scoring.domains:
        return None
    return scoring


def _bar_percent(score: float) -> int:
    span = DEFAULT_SCALE_MAX - DEFAULT_SCALE_MIN
    if span <= 0:
        return 0
    percent = (score - DEFAULT_SCALE_MIN) / span * 100
    return max(0, min(100, round(percent)))


def answer_row(
    session: Session, answer: SessionAnswer, note: str = ""
) -> dict[str, Any]:
    return {
        "order_number": answer.link.order_num,
        "display_num": answer.link.display_num,
        "question_text": answer.question.text,
        "category_name": group_label(session, answer.link.group),
        "answer": answer.display_value,
        "legend": answer.legend,
        "show_bar": answer.progress["show_bar"],
        "bar_percent": answer.progress["percent"],
        "bar_color": answer.progress["color"],
        "scored_note": note,
    }


def _point_note(point: ScoredPoint) -> str:
    if point.reversed and point.scored is not None:
        return f"в балл: {DEFAULT_SCALE_MAX} − x = {point.scored}"
    return ""


def _point_rows(
    session: Session, points: tuple[ScoredPoint, ...]
) -> list[dict[str, Any]]:
    return [answer_row(session, point.answer, _point_note(point)) for point in points]


def scoring_view(session: Session, scoring: DomainScoring) -> dict[str, Any]:
    sections: list[dict[str, Any]] = []
    for domain in scoring.domains:
        color = dictionary_service.group_color(session, domain.key)
        sections.append(
            {
                "key": domain.key,
                "label": group_label(session, domain.key),
                "score_label": (
                    "—" if domain.score is None else f"{(domain.score / 4 * 10):.2f}"
                ),
                "answered": domain.answered,
                "total": domain.total,
                "low_answers": domain.score is None,
                "expanded": (
                    domain.score is not None and domain.score >= DOMAIN_OPEN_SCORE
                ),
                "show_bar": domain.score is not None,
                "bar_percent": (
                    0 if domain.score is None else _bar_percent(domain.score)
                ),
                "bar_color": color,
                "items": _point_rows(session, domain.points),
            }
        )
    unscored = [answer_row(session, answer) for answer in scoring.unscored]
    return {"domains": sections, "unscored": unscored}
