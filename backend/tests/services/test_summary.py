import uuid

from sqlmodel import Session

from app.models import Dog, Owner, Question, SurveyQuestion
from app.services.scoring import ScoringConsts, score_domains
from app.services.sessions import SessionAnswer
from app.services.summary import (
    CONCERN_DOMAIN_MIN,
    PROMPT_VERSION,
    anonymize_history,
    build_facts,
    facts_fingerprint,
    rules_view,
    validate_llm_summary,
)


def _answer(
    order: int,
    value: object | None,
    text: str = "Вопрос",
    group: str = "other",
) -> SessionAnswer:
    from app.models import AnswerEvent

    question_id = uuid.uuid4()
    version_id = uuid.uuid4()
    question = Question(id=question_id, text=text, scale_id=uuid.uuid4())
    link = SurveyQuestion(
        survey_version_id=version_id,
        question_id=question_id,
        order_num=order,
        display_num=order,
        group=group,
    )
    event = None
    if value is not None:
        event = AnswerEvent(
            surveys_session_id=uuid.uuid4(),
            survey_version_id=version_id,
            question_id=question_id,
            value={"value": value},
        )
    shown = "" if value is None else str(value)
    return SessionAnswer(
        question=question,
        link=link,
        event=event,
        display_value=shown,
        legend="",
        progress={"show_bar": False, "percent": 0, "color": "blue"},
    )


def test_build_facts_strengths_concerns_and_red_flag(db: Session) -> None:
    answers = [
        _answer(1, 0, "Спокойна с гостями", group="Excitability"),
        _answer(2, 0, "Спокойна на улице", group="Excitability"),
        _answer(10, 4, "Кусается", group="Aggression"),
        _answer(11, 3, "Рычит", group="Aggression"),
        _answer(20, 1, "Боится грома", group="Fear_Anxiety"),
    ]
    scoring = score_domains(answers, ScoringConsts(None, frozenset()))
    facts = build_facts(
        db,
        scoring,
        answers,
        {
            "sex": "самка",
            "status": "дом",
            "days_since_status": 14,
            "age": "2 г. 3 мес.",
            "breed": "лабрадор",
            "mixed": False,
            "neutered": True,
            "weight": 28.5,
            "history": "Взяли 14 дней назад",
        },
    )
    assert any(": 0.00 из 10" in line for line in facts.overview)
    assert any("0.00 из 10" in item.text for item in facts.strengths)
    assert any(": " in item.text and "из 10" in item.text for item in facts.concerns)
    assert any(
        "п. 10" in item.text and "10 из 10" in item.text for item in facts.concerns
    )
    assert any(
        "п. 11" in item.text and "7 из 10" in item.text for item in facts.concerns
    )
    assert len(facts.red_flags) == 1
    assert facts.red_flags[0].refs == (10,)
    assert "Пол: самка" in facts.dog
    assert "Статус: дом, 14 дн." in facts.dog
    assert "Стерилизована: да" in facts.dog
    assert 10 in facts.allowed_refs
    assert "10" in facts.allowed_numbers
    assert "28.5" in facts.allowed_numbers or "28.50" in facts.allowed_numbers


def test_build_facts_gaps_and_fallback_strength(db: Session) -> None:
    answers = [
        _answer(1, 2, group="Excitability"),
        _answer(2, None, group="Excitability"),
        _answer(3, -1, group="Excitability"),
        _answer(4, -999, group="Excitability"),
        _answer(27, 1, group="Training"),
        _answer(28, None, group="Training"),
        _answer(29, None, group="Training"),
    ]
    # Threshold 0.5: Excitability answered 1/4 → no score; Training 1/3 → no score
    scoring = score_domains(answers, ScoringConsts(0.5, frozenset({27})))
    facts = build_facts(db, scoring, answers, {})
    assert facts.overview == ()
    assert facts.strengths == ()
    assert any("мало ответов" in gap for gap in facts.gaps)
    assert "Не наблюдалось: 1" in facts.gaps
    assert "Пропусков (−999): 1" in facts.gaps

    mid = [
        _answer(1, 1, group="Excitability"),
        _answer(2, 1, group="Excitability"),
        _answer(10, 2, group="Aggression"),
        _answer(11, 2, group="Aggression"),
    ]
    scoring = score_domains(mid, ScoringConsts(None, frozenset()))
    facts = build_facts(db, scoring, mid, {})
    # Both domains below concern min; strengths take the lowest under concern min.
    assert facts.strengths
    assert all(
        float(item.text.split(": ", 1)[1].split(" из ", 1)[0]) < CONCERN_DOMAIN_MIN
        for item in facts.strengths
    )


def test_build_facts_reverse_items_in_concerns(db: Session) -> None:
    answers = [
        _answer(27, 0, "Слушается", group="Training"),
        _answer(28, 0, "Приходит", group="Training"),
    ]
    scoring = score_domains(answers, ScoringConsts(None, frozenset({27, 28})))
    facts = build_facts(db, scoring, answers, {})
    assert any("10.00 из 10" in line for line in facts.overview)
    assert any("10 из 10" in item.text for item in facts.concerns)


def test_rules_view_narrative_from_facts(db: Session) -> None:
    answers = [
        _answer(1, 4, group="Excitability"),
        _answer(2, 4, group="Excitability"),
        _answer(10, 0, group="Aggression"),
        _answer(11, 0, group="Aggression"),
    ]
    scoring = score_domains(answers, ScoringConsts(None, frozenset()))
    facts = build_facts(db, scoring, answers, {})
    view = rules_view(facts, anonymized_history="Взяли недавно")
    assert "narrative" in view
    assert "Взяли недавно" in view["narrative"]
    assert "По анкете:" in view["narrative"]
    assert "10.00 из 10" in view["narrative"]
    assert "0.00 из 10" in view["narrative"]


def test_anonymize_history_masks_pii() -> None:
    owner = Owner(
        name="Иван Петров",
        email="ivan@example.com",
        phone="+7 900 111-22-33",
        contact="@ivan_tg",
    )
    dog = Dog(name="Рекс")
    text = (
        "Рекс живёт у Иван Петров, пишите ivan@example.com или +7 900 111-22-33, "
        "телега @ivan_tg, сайт https://example.com/dog"
    )
    cleaned = anonymize_history(text, owner, dog)
    assert "Рекс" not in cleaned
    assert "Иван" not in cleaned
    assert "ivan@example.com" not in cleaned
    assert "+7 900 111-22-33" not in cleaned
    assert "@ivan_tg" not in cleaned
    assert "https://example.com/dog" not in cleaned
    assert "собака" in cleaned
    assert "[владелец]" in cleaned
    assert "[контакт]" in cleaned
    assert "[телефон]" in cleaned


def test_facts_fingerprint_changes_with_answer_and_history(db: Session) -> None:
    base = [
        _answer(1, 2, group="Excitability"),
        _answer(2, 2, group="Excitability"),
    ]
    scoring = score_domains(base, ScoringConsts(None, frozenset()))
    facts = build_facts(db, scoring, base, {"history": "Была в приюте 3 месяца"})
    first = facts_fingerprint(
        facts,
        anonymized_history="Была в приюте 3 месяца",
        model="GigaChat-2-Max",
    )
    changed_answers = [
        _answer(1, 4, group="Excitability"),
        _answer(2, 2, group="Excitability"),
    ]
    scoring2 = score_domains(changed_answers, ScoringConsts(None, frozenset()))
    facts2 = build_facts(
        db, scoring2, changed_answers, {"history": "Была в приюте 3 месяца"}
    )
    second = facts_fingerprint(
        facts2,
        anonymized_history="Была в приюте 3 месяца",
        model="GigaChat-2-Max",
    )
    third = facts_fingerprint(
        facts,
        anonymized_history="Была в приюте 5 месяцев",
        model="GigaChat-2-Max",
    )
    assert first != second
    assert first != third
    assert len(first) == 64
    assert PROMPT_VERSION


def test_validate_llm_summary_accepts_and_rejects(db: Session) -> None:
    answers = [
        _answer(1, 4, group="Excitability"),
        _answer(2, 0, group="Excitability"),
        _answer(10, 0, group="Aggression"),
        _answer(11, 0, group="Aggression"),
    ]
    scoring = score_domains(answers, ScoringConsts(None, frozenset()))
    facts = build_facts(db, scoring, answers, {})
    ok = {
        "narrative": (
            "У нас собака уже почти 3 недели. По анкете заметна возбудимость, "
            "агрессии почти нет."
        ),
    }
    assert validate_llm_summary(ok, facts) == ok
    assert validate_llm_summary({"narrative": "Поставлен диагноз"}, facts) is None
    assert validate_llm_summary({"narrative": ""}, facts) is None
    assert validate_llm_summary({"headline": "старый формат"}, facts) is None
