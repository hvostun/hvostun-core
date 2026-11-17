"""Compare a dog-profile question with and without the local RAG index."""

import asyncio
import uuid
from dataclasses import dataclass
from datetime import date

import httpx
from sqlmodel import Session, col, select

from app.core.config import settings
from app.models import Dog, Owner, SurveySession
from app.services import dictionaries as dictionary_service
from app.services import sessions as session_service
from app.services.summary import anonymize_history, parse_stored_summary


@dataclass(frozen=True)
class DogSessionView:
    row: SurveySession
    fill_rate: int | None
    has_narrative: bool


@dataclass(frozen=True)
class RagAnswer:
    mode: str
    answer: str | None
    error: str | None


def list_dog_sessions(session: Session, dog_id: uuid.UUID) -> list[DogSessionView]:
    rows = list(
        session.exec(
            select(SurveySession)
            .where(SurveySession.dog_id == dog_id)
            .order_by(
                col(SurveySession.created_at).desc(),
                col(SurveySession.id).desc(),
            )
        )
    )
    rates = session_service.answer_rates(session, [row.id for row in rows])
    return [
        DogSessionView(
            row=row,
            fill_rate=rates[row.id],
            has_narrative=parse_stored_summary(row.summary) is not None,
        )
        for row in rows
    ]


def _labeled(session: Session, key: str, code: str | None) -> str:
    if not code:
        return ""
    return dictionary_service.label_for(session, key, code) or code


def _yes_no(value: bool | None) -> str:
    if value is None:
        return ""
    return "да" if value else "нет"


def build_hybrid_system_prompt(
    session: Session,
    dog: Dog,
    latest: SurveySession | None,
) -> str:
    """Dog profile for the hybrid call. Owner, volunteer and shelter stay out."""
    owner = session.get(Owner, dog.owner_id) if dog.owner_id else None
    today = date.today()
    fields: list[tuple[str, str]] = [
        ("Имя", dog.name),
        ("Пол", _labeled(session, dictionary_service.DOGS_SEX_KEY, dog.sex)),
        ("Возраст", session_service.format_dog_age(dog.birthday, today)),
        ("Порода", dog.breed or ""),
        ("Метис", _yes_no(dog.mixed)),
        ("Стерилизация", _yes_no(dog.neutered)),
        (
            "Статус",
            _labeled(session, dictionary_service.DOGS_STATUS_KEY, str(dog.status)),
        ),
        ("Дата статуса", dog.status_at.isoformat() if dog.status_at else ""),
        ("Вес", "" if dog.weight is None else str(dog.weight)),
        ("Рост", "" if dog.height is None else str(dog.height)),
        ("Описание", (dog.description or "").strip()),
        ("История", anonymize_history(dog.history, owner).strip()),
    ]
    lines = ["Данные собаки из профиля:"]
    lines.extend(f"{label}: {value}" for label, value in fields if value)
    if latest is not None:
        stored = parse_stored_summary(latest.summary)
        if stored is not None:
            when = ""
            if latest.created_at is not None:
                when = latest.created_at.strftime("%d.%m.%Y")
            lines.append("")
            lines.append(f"Сводка последней анкеты ({when}):")
            lines.append(stored.narrative)
    return "\n".join(lines)


async def _query(
    client: httpx.AsyncClient,
    mode: str,
    payload: dict[str, str],
) -> RagAnswer:
    base = (settings.RAG_URL or "").rstrip("/")
    try:
        response = await client.post(f"{base}/query", json=payload)
        response.raise_for_status()
        body = response.json()
    except httpx.HTTPError as exc:
        return RagAnswer(mode, None, str(exc))
    except ValueError as exc:
        return RagAnswer(mode, None, str(exc))
    answer = body.get("answer") if isinstance(body, dict) else None
    if not isinstance(answer, str) or not answer.strip():
        return RagAnswer(mode, None, "пустой ответ")
    return RagAnswer(mode, answer, None)


async def ask_both(
    question: str,
    system_prompt: str,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> tuple[RagAnswer, RagAnswer]:
    """Ask the RAG service in bypass and hybrid. One failure does not cancel the other."""
    if not settings.RAG_URL:
        missing = RagAnswer("bypass", None, "RAG не настроен")
        return missing, RagAnswer("hybrid", None, "RAG не настроен")
    timeout = httpx.Timeout(settings.RAG_TIMEOUT_SECONDS)
    async with httpx.AsyncClient(transport=transport, timeout=timeout) as client:
        bypass, hybrid = await asyncio.gather(
            _query(client, "bypass", {"query": question, "mode": "bypass"}),
            _query(
                client,
                "hybrid",
                {
                    "query": question,
                    "mode": "hybrid",
                    "system_prompt": system_prompt,
                },
            ),
        )
    return bypass, hybrid
