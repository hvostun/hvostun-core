import asyncio
import json
import uuid
from datetime import UTC, date, datetime

import httpx
import pytest
from sqlmodel import Session

from app.core.config import settings
from app.models import Dog, Owner, Shelter, Survey, SurveySession, SurveyVersion, User
from app.services.rag_compare import (
    ask_both,
    build_hybrid_system_prompt,
    list_dog_sessions,
)
from app.services.sessions import format_dog_age


def _summary(narrative: str) -> dict[str, object]:
    return {
        "fingerprint": "a" * 64,
        "model": "GigaChat-2-Max",
        "prompt_version": "v1",
        "generated_at": "2026-11-01T00:00:00Z",
        "generated_by": str(uuid.uuid4()),
        "narrative": narrative,
    }


def _dog_with_people(db: Session) -> tuple[Dog, SurveyVersion]:
    owner_email = f"secret-owner-{uuid.uuid4()}@example.com"
    owner = Owner(
        name="Секретный Владелец",
        email=owner_email,
        phone="+7 900 111-22-33",
    )
    shelter = Shelter(name="Секретный Приют")
    volunteer = User(
        email=f"volunteer-{uuid.uuid4()}@example.com",
        hashed_password="not-used",
        full_name="Секретный Волонтёр",
    )
    db.add(owner)
    db.add(shelter)
    db.add(volunteer)
    db.commit()
    db.refresh(owner)
    db.refresh(shelter)
    db.refresh(volunteer)
    dog = Dog(
        name="Рекс",
        sex="female",
        neutered=False,
        status="home",
        description="спокойная",
        shelter_id=shelter.id,
        assigned_volunteer_id=volunteer.id,
        owner_id=owner.id,
        birthday=date(2024, 1, 15),
        status_at=date(2026, 9, 1),
        breed="лабрадор",
        mixed=True,
        weight=12.5,
        height=48,
        history=f"Живёт у Секретный Владелец, почта {owner_email}",
    )
    survey = Survey(name="RAG compare", slug=f"rag-compare-{uuid.uuid4()}")
    db.add(dog)
    db.add(survey)
    db.commit()
    db.refresh(dog)
    db.refresh(survey)
    version = SurveyVersion(survey_id=survey.id, version_num=1)
    db.add(version)
    db.commit()
    db.refresh(version)
    assert dog.owner_id is not None
    return dog, version


def test_hybrid_prompt_uses_profile_and_latest_narrative(db: Session) -> None:
    dog, version = _dog_with_people(db)
    assert dog.owner_id is not None
    older = SurveySession(
        owner_id=dog.owner_id,
        dog_id=dog.id,
        survey_version_id=version.id,
        status="draft",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        summary=_summary("старый рассказ"),
    )
    newer = SurveySession(
        owner_id=dog.owner_id,
        dog_id=dog.id,
        survey_version_id=version.id,
        status="finished",
        created_at=datetime(2026, 11, 1, tzinfo=UTC),
        summary=_summary("свежий рассказ"),
    )
    db.add(older)
    db.add(newer)
    db.commit()

    listed = list_dog_sessions(db, dog.id)
    assert [item.row.id for item in listed] == [newer.id, older.id]
    assert listed[0].has_narrative is True

    prompt = build_hybrid_system_prompt(db, dog, listed[0].row)
    assert "Имя: Рекс" in prompt
    assert "Пол: female" in prompt
    assert f"Возраст: {format_dog_age(dog.birthday, date.today())}" in prompt
    assert "Порода: лабрадор" in prompt
    assert "Метис: да" in prompt
    assert "Стерилизация: нет" in prompt
    assert "Статус: home" in prompt
    assert "Дата статуса: 2026-09-01" in prompt
    assert "Вес: 12.5" in prompt
    assert "Рост: 48" in prompt
    assert "Описание: спокойная" in prompt
    assert "свежий рассказ" in prompt
    assert "Сводка последней анкеты (01.11.2026):" in prompt
    assert "старый рассказ" not in prompt
    assert "Секретный Владелец" not in prompt
    assert "Секретный Волонтёр" not in prompt
    assert "Секретный Приют" not in prompt
    assert "secret-owner-" not in prompt
    assert "[владелец]" in prompt
    assert "[контакт]" in prompt


def test_hybrid_prompt_skips_summary_without_narrative(db: Session) -> None:
    dog, version = _dog_with_people(db)
    assert dog.owner_id is not None
    row = SurveySession(
        owner_id=dog.owner_id,
        dog_id=dog.id,
        survey_version_id=version.id,
        status="draft",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    prompt = build_hybrid_system_prompt(db, dog, row)
    assert "Имя: Рекс" in prompt
    assert "Сводка" not in prompt


def test_ask_both_sends_modes_and_isolates_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "RAG_URL", "http://rag.test")
    seen: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen.append(body)
        if body["mode"] == "hybrid":
            return httpx.Response(502, json={"detail": "down"})
        return httpx.Response(200, json={"answer": "без базы"})

    bypass, hybrid = asyncio.run(
        ask_both(
            "Как гулять?",
            "контекст собаки",
            transport=httpx.MockTransport(handler),
        )
    )
    by_mode = {item["mode"]: item for item in seen}
    assert set(by_mode) == {"bypass", "hybrid"}
    assert "system_prompt" not in by_mode["bypass"]
    assert by_mode["bypass"]["query"] == "Как гулять?"
    assert by_mode["hybrid"]["system_prompt"] == "контекст собаки"
    assert by_mode["hybrid"]["query"] == "Как гулять?"
    assert bypass.answer == "без базы"
    assert bypass.error is None
    assert hybrid.answer is None
    assert hybrid.error
