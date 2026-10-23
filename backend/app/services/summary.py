"""Rule-based session summary facts for the expert contour.

Scores and thresholds use the expert 10-point scale. Storage stays 0–4.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from sqlmodel import Session

from app.models import Dog, Owner, SurveyQuestionGroup
from app.services import gigachat as gigachat_service
from app.services import scoring as scoring_service
from app.services import sessions as session_service
from app.services.scoring import DomainScore, DomainScoring, ScoredPoint
from app.services.sessions import (
    EXPERT_SCALE_MAX,
    MISSING_ANSWER,
    SessionAnswer,
    SessionContext,
    answer_scalar,
    group_label,
)

PROMPT_VERSION = "2026-10-16.7"
STRENGTH_DOMAIN_MAX = 3.0
CONCERN_DOMAIN_MIN = 5.0
CONCERN_ITEM_MIN = 7
CONCERN_ITEM_LIMIT = 5
# Domain key → expert points threshold for a red flag on a single item.
RED_FLAGS: dict[str, int] = {
    SurveyQuestionGroup.AGGRESSION: EXPERT_SCALE_MAX,
}
UNOBSERVED_ANSWER = -1

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
_PHONE_RE = re.compile(r"\+?\d[\d\s\-()]{8,}\d")
_NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)?")
_FORBIDDEN_WORDS = ("диагноз", "препарат", "наказ")
_NARRATIVE_MAX = 4000


@dataclass(frozen=True)
class FactItem:
    text: str
    refs: tuple[int, ...]


@dataclass(frozen=True)
class SummaryFacts:
    overview: tuple[str, ...]
    strengths: tuple[FactItem, ...]
    concerns: tuple[FactItem, ...]
    red_flags: tuple[FactItem, ...]
    gaps: tuple[str, ...]
    dog: tuple[str, ...]
    allowed_refs: frozenset[int]
    allowed_numbers: frozenset[str]


def anonymize_history(text: str | None, owner: Owner, dog: Dog) -> str:
    if not text:
        return ""
    result = text
    for value, replacement in (
        (owner.email, "[контакт]"),
        (owner.phone, "[телефон]"),
        (owner.contact, "[контакт]"),
        (owner.name, "[владелец]"),
        (dog.name, "собака"),
    ):
        if value:
            result = re.sub(re.escape(value), replacement, result, flags=re.IGNORECASE)
    result = _EMAIL_RE.sub("[контакт]", result)
    result = _URL_RE.sub("[контакт]", result)
    result = _PHONE_RE.sub("[телефон]", result)
    return result


def _refs_for_domain(domain: DomainScore) -> tuple[int, ...]:
    return tuple(
        sorted(
            {
                point.answer.link.display_num
                for point in domain.points
                if point.points is not None
            }
        )
    )


def _domain_line(label: str, score: float) -> str:
    return f"{label}: {score:.2f} из {EXPERT_SCALE_MAX}"


def _item_line(point: ScoredPoint, label: str) -> str:
    assert point.points is not None
    text = point.answer.question.text.strip() or "вопрос"
    return (
        f"{label}, п. {point.answer.link.display_num}: "
        f"{text} — {point.points} из {EXPERT_SCALE_MAX}"
    )


def _is_female_sex(sex: str) -> bool:
    lowered = sex.casefold().strip()
    if lowered in {"f", "female", "ж", "жен", "женский"}:
        return True
    return any(
        marker in lowered for marker in ("female", "сука", "самка", "девоч", "женск")
    )


def _is_male_sex(sex: str) -> bool:
    lowered = sex.casefold().strip()
    if lowered in {"m", "male", "м", "муж", "мужской"}:
        return True
    # Avoid matching the "male" inside "female".
    if "female" in lowered:
        return False
    return any(
        marker in lowered for marker in ("male", "кобель", "самец", "мальчик", "мужск")
    )


def _dog_lines(dog_facts: dict[str, Any]) -> tuple[str, ...]:
    lines: list[str] = []
    sex = str(dog_facts.get("sex") or "").strip()
    if sex:
        lines.append(f"Пол: {sex}")
    status = str(dog_facts.get("status") or "").strip()
    days = dog_facts.get("days_since_status")
    if status and days is not None:
        lines.append(f"Статус: {status}, {days} дн.")
    elif status:
        lines.append(f"Статус: {status}")
    age = str(dog_facts.get("age") or "").strip()
    if age:
        lines.append(f"Возраст: {age}")
    breed = str(dog_facts.get("breed") or "").strip()
    if breed:
        mixed = " (метис)" if dog_facts.get("mixed") else ""
        lines.append(f"Порода: {breed}{mixed}")
    if dog_facts.get("neutered") is not None:
        if sex and _is_female_sex(sex):
            label = "Стерилизована"
        elif sex and _is_male_sex(sex):
            label = "Стерилизован"
        else:
            label = "Стерилизация"
        lines.append(f"{label}: {'да' if dog_facts['neutered'] else 'нет'}")
    weight = dog_facts.get("weight")
    if weight is not None:
        lines.append(f"Вес: {weight}")
    return tuple(lines)


def _collect_numbers(*parts: object) -> set[str]:
    found: set[str] = set()
    for part in parts:
        if part is None:
            continue
        if isinstance(part, bool):
            continue
        if isinstance(part, int | float):
            if isinstance(part, float) and part.is_integer():
                found.add(str(int(part)))
            else:
                found.add(str(part))
                found.add(f"{part:.2f}" if isinstance(part, float) else str(part))
            continue
        text = str(part)
        for match in _NUMBER_RE.findall(text):
            found.add(match)
            found.add(match.replace(",", "."))
            if "." in match.replace(",", "."):
                try:
                    found.add(f"{float(match.replace(',', '.')):.2f}")
                except ValueError:
                    pass
    return found


def _count_special_answers(answers: list[SessionAnswer]) -> tuple[int, int]:
    unobserved = 0
    missing = 0
    for answer in answers:
        if answer.event is None:
            continue
        scalar = answer_scalar(answer.event.value)
        if scalar == UNOBSERVED_ANSWER:
            unobserved += 1
        elif scalar == MISSING_ANSWER:
            missing += 1
    return unobserved, missing


def build_facts(
    session: Session,
    scoring: DomainScoring | None,
    answers: list[SessionAnswer],
    dog_facts: dict[str, Any],
) -> SummaryFacts:
    domains = () if scoring is None else scoring.domains
    overview: list[str] = []
    strengths: list[FactItem] = []
    concerns: list[FactItem] = []
    red_flags: list[FactItem] = []
    gaps: list[str] = []
    allowed_refs: set[int] = set()
    numbers: set[str] = set()
    scored_domains: list[tuple[str, float, DomainScore]] = []

    for domain in domains:
        label = group_label(session, domain.key) or domain.key
        for point in domain.points:
            allowed_refs.add(point.answer.link.display_num)
            numbers |= _collect_numbers(
                point.answer.link.display_num,
                point.points,
                point.raw,
                point.scored,
            )
        if domain.score is None:
            gaps.append(f"{label}: мало ответов ({domain.answered} из {domain.total})")
            numbers |= _collect_numbers(domain.answered, domain.total)
            continue
        overview.append(_domain_line(label, domain.score))
        scored_domains.append((label, domain.score, domain))
        numbers |= _collect_numbers(domain.score, f"{domain.score:.2f}")

        threshold = RED_FLAGS.get(domain.key)
        if threshold is not None:
            for point in domain.points:
                if point.points == threshold:
                    red_flags.append(
                        FactItem(
                            text=_item_line(point, label),
                            refs=(point.answer.link.display_num,),
                        )
                    )

    strength_domains = [
        (label, score, domain)
        for label, score, domain in scored_domains
        if score <= STRENGTH_DOMAIN_MAX
    ]
    if not strength_domains and scored_domains:
        label, score, domain = min(scored_domains, key=lambda item: item[1])
        if score < CONCERN_DOMAIN_MIN:
            strength_domains = [(label, score, domain)]
    for label, score, domain in sorted(strength_domains, key=lambda item: item[1]):
        strengths.append(
            FactItem(text=_domain_line(label, score), refs=_refs_for_domain(domain))
        )

    concern_domains = [
        (label, score, domain)
        for label, score, domain in scored_domains
        if score >= CONCERN_DOMAIN_MIN
    ]
    for label, score, domain in sorted(
        concern_domains, key=lambda item: (-item[1], item[0])
    ):
        concerns.append(
            FactItem(text=_domain_line(label, score), refs=_refs_for_domain(domain))
        )

    high_items: list[tuple[int, int, str, ScoredPoint]] = []
    for label, _score, domain in scored_domains:
        for point in domain.points:
            if point.points is not None and point.points >= CONCERN_ITEM_MIN:
                high_items.append(
                    (point.points, point.answer.link.display_num, label, point)
                )
    high_items.sort(key=lambda item: (-item[0], item[1]))
    for _points, display_num, label, point in high_items[:CONCERN_ITEM_LIMIT]:
        concerns.append(FactItem(text=_item_line(point, label), refs=(display_num,)))

    unobserved, missing = _count_special_answers(answers)
    if unobserved:
        gaps.append(f"Не наблюдалось: {unobserved}")
        numbers |= _collect_numbers(unobserved)
    if missing:
        gaps.append(f"Пропусков (−999): {missing}")
        numbers |= _collect_numbers(missing)

    dog_lines = _dog_lines(dog_facts)
    numbers |= _collect_numbers(
        EXPERT_SCALE_MAX,
        STRENGTH_DOMAIN_MAX,
        CONCERN_DOMAIN_MIN,
        CONCERN_ITEM_MIN,
        *dog_lines,
        dog_facts.get("days_since_status"),
        dog_facts.get("weight"),
        dog_facts.get("height"),
    )
    history = dog_facts.get("history")
    if history:
        numbers |= _collect_numbers(history)

    return SummaryFacts(
        overview=tuple(overview),
        strengths=tuple(strengths),
        concerns=tuple(concerns),
        red_flags=tuple(red_flags),
        gaps=tuple(gaps),
        dog=dog_lines,
        allowed_refs=frozenset(allowed_refs),
        allowed_numbers=frozenset(numbers),
    )


def _headline(facts: SummaryFacts) -> str:
    ranked: list[tuple[float, str]] = []
    for line in facts.overview:
        # "Label: 7.50 из 10"
        if ": " not in line or " из " not in line:
            continue
        label, rest = line.split(": ", 1)
        score_text = rest.split(" из ", 1)[0]
        try:
            ranked.append((float(score_text), label))
        except ValueError:
            continue
    ranked.sort(key=lambda item: (-item[0], item[1]))
    top = ranked[:2]
    if not top:
        return "По анкете недостаточно данных для сводки."
    if len(top) == 1:
        score, label = top[0]
        return f"Наиболее выражена шкала «{label}» ({score:.2f} из {EXPERT_SCALE_MAX})."
    (s1, l1), (s2, l2) = top
    return (
        f"Наиболее выражены шкалы «{l1}» ({s1:.2f} из {EXPERT_SCALE_MAX}) "
        f"и «{l2}» ({s2:.2f} из {EXPERT_SCALE_MAX})."
    )


def _items_as_dicts(items: tuple[FactItem, ...]) -> list[dict[str, Any]]:
    return [{"text": item.text, "refs": list(item.refs)} for item in items]


def rules_view(
    facts: SummaryFacts,
    *,
    anonymized_history: str = "",
) -> dict[str, Any]:
    """Plain fallback narrative when GigaChat is off or rejected."""
    parts: list[str] = []
    if facts.dog:
        parts.append(" ".join(facts.dog) + ".")
    history = anonymized_history.strip()
    if history:
        parts.append(history)
    observed: list[str] = []
    for item in (*facts.concerns, *facts.strengths):
        observed.append(item.text.rstrip("."))
    if observed:
        parts.append("По анкете: " + "; ".join(observed) + ".")
    if not parts:
        parts.append(_headline(facts))
    return {"narrative": "\n\n".join(parts)}


def facts_payload(facts: SummaryFacts) -> dict[str, Any]:
    return {
        "overview": list(facts.overview),
        "strengths": _items_as_dicts(facts.strengths),
        "concerns": _items_as_dicts(facts.concerns),
        "red_flags": _items_as_dicts(facts.red_flags),
        "gaps": list(facts.gaps),
        "dog": list(facts.dog),
        "allowed_refs": sorted(facts.allowed_refs),
    }


def facts_fingerprint(
    facts: SummaryFacts,
    *,
    anonymized_history: str,
    prompt_version: str = PROMPT_VERSION,
    model: str,
) -> str:
    payload = {
        "facts": facts_payload(facts),
        "history": anonymized_history,
        "prompt_version": prompt_version,
        "model": model,
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


class LlmSummaryDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    narrative: str = Field(min_length=1, max_length=_NARRATIVE_MAX)

    @field_validator("narrative")
    @classmethod
    def _strip_narrative(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("empty narrative")
        return text


class SessionSummaryStored(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fingerprint: str
    model: str
    prompt_version: str
    generated_at: datetime
    generated_by: uuid.UUID
    narrative: str


def parse_stored_summary(value: object) -> SessionSummaryStored | None:
    if not isinstance(value, dict):
        return None
    try:
        return SessionSummaryStored.model_validate(value)
    except ValidationError:
        return None


def _text_has_forbidden_words(text: str) -> bool:
    lowered = text.casefold()
    return any(word in lowered for word in _FORBIDDEN_WORDS)


def validate_llm_summary(raw: object, _facts: SummaryFacts) -> dict[str, Any] | None:
    """Parse and check an LLM narrative. Returns dict or None.

    Narrative is free-form owner speech: only schema + forbidden words.
    """
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return None
    try:
        draft = LlmSummaryDraft.model_validate(raw)
    except ValidationError:
        return None
    if _text_has_forbidden_words(draft.narrative):
        return None
    return {"narrative": draft.narrative}


@dataclass(frozen=True)
class SummaryGenerateOutcome:
    status: Literal["ok", "skipped", "error"]
    detail: str
    stored: SessionSummaryStored | None = None


def generate_and_store_summary(
    session: Session,
    context: SessionContext,
    *,
    generated_by: uuid.UUID,
    force: bool = False,
    model: str | None = None,
    client: gigachat_service.GigaChatClient | None = None,
) -> SummaryGenerateOutcome:
    """Call GigaChat, validate narrative, persist on the survey session.

    ``model`` overrides the client/env default for this call (fingerprint includes it).
    """
    chat = client or gigachat_service.get_client()
    if not chat.enabled:
        return SummaryGenerateOutcome("error", "GigaChat не настроен")
    effective_model = (model or chat.model).strip() or chat.model

    answers = session_service.get_session_answers(session, context.row)
    scoring = scoring_service.score_session(session, answers)
    dog_facts = session_service.dog_session_facts(session, context.dog, context.row)
    facts = build_facts(session, scoring, answers, dog_facts)
    anonymized = anonymize_history(
        dog_facts.get("history") if isinstance(dog_facts.get("history"), str) else None,
        context.owner,
        context.dog,
    )
    fingerprint = facts_fingerprint(
        facts,
        anonymized_history=anonymized,
        model=effective_model,
    )
    if not force:
        existing = parse_stored_summary(context.row.summary)
        if existing is not None and existing.fingerprint == fingerprint:
            return SummaryGenerateOutcome(
                "skipped",
                "уже есть свежий рассказ",
                stored=existing,
            )

    try:
        raw = chat.rewrite_summary(
            facts_payload=facts_payload(facts),
            anonymized_history=anonymized,
            model=effective_model,
        )
    except gigachat_service.GigaChatError as exc:
        return SummaryGenerateOutcome("error", str(exc))

    validated = validate_llm_summary(raw, facts)
    if validated is None:
        return SummaryGenerateOutcome("error", "ответ не прошёл проверку")

    stored = SessionSummaryStored(
        fingerprint=fingerprint,
        model=effective_model,
        prompt_version=PROMPT_VERSION,
        generated_at=datetime.now(UTC),
        generated_by=generated_by,
        narrative=validated["narrative"],
    )
    context.row.summary = stored.model_dump(mode="json")
    session.add(context.row)
    session.commit()
    session.refresh(context.row)
    return SummaryGenerateOutcome("ok", "сохранено", stored=stored)
