import uuid
from datetime import UTC, datetime

from sqlalchemy import text
from sqlmodel import Session

from app.models import (
    AnswerEvent,
    Dog,
    Owner,
    Question,
    Scale,
    Survey,
    SurveyQuestion,
    SurveySession,
    SurveyVersion,
)
from app.services.scoring import (
    ScoringConsts,
    parse_scoring_consts,
    score_domains,
    score_session,
)
from app.services.sessions import SessionAnswer, answer_rates
from tests.utils.utils import random_lower_string


def _consts(
    threshold: float | None = 0.5, reverse: frozenset[int] = frozenset({27, 28})
) -> ScoringConsts:
    return ScoringConsts(threshold, reverse)


def _answer(
    order: int,
    value: object | None,
    text: str = "Вопрос",
    group: str = "other",
) -> SessionAnswer:
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


def test_parse_scoring_consts_ignores_garbage() -> None:
    parsed = parse_scoring_consts(
        {
            "c-barq-short-42": {
                "domain_threshold": 0.5,
                "reverse": [27, 27, True, "x", 28],
            }
        }
    )
    assert parsed.threshold == 0.5
    assert parsed.reverse == frozenset({27, 28})
    assert parse_scoring_consts(None) == ScoringConsts(None, frozenset())
    assert parse_scoring_consts({"c-barq-short-42": {}}).threshold is None
    assert (
        parse_scoring_consts({"c-barq-short-42": {"domain_threshold": True}}).threshold
        is None
    )


def test_score_domains_groups_by_question_group() -> None:
    answers = [
        _answer(1, 2, group="Excitability"),
        _answer(2, -999, group="Excitability"),
        _answer(27, 0, group="Trainability"),
        _answer(28, 4, group="Trainability"),
        _answer(29, 1, group="Trainability"),
        _answer(99, 1, "вне", group="other"),
    ]
    result = score_domains(answers, _consts())
    excitability, training = result.domains
    assert [domain.key for domain in result.domains] == [
        "Excitability",
        "Trainability",
    ]
    assert excitability.answered == 1
    assert excitability.total == 2
    assert excitability.score == 2.0
    assert training.score == 1.67
    assert training.points[0].scored == 4
    assert training.points[0].reversed is True
    assert training.points[1].scored == 0
    assert [item.question.text for item in result.unscored] == ["вне"]
    below = score_domains(
        [
            _answer(27, 0, group="Trainability"),
            _answer(28, None, group="Trainability"),
            _answer(29, None, group="Trainability"),
        ],
        _consts(reverse=frozenset({27})),
    )
    assert below.domains[0].answered == 1
    assert below.domains[0].score is None


def test_score_domains_without_threshold_uses_any_answer() -> None:
    result = score_domains(
        [
            _answer(1, 2, group="Excitability"),
            _answer(2, -999, group="Excitability"),
        ],
        ScoringConsts(None, frozenset()),
    )
    assert result.domains[0].score == 2.0


def test_score_domains_skips_non_integers() -> None:
    result = score_domains(
        [
            _answer(1, "часто", group="Excitability"),
            _answer(2, 2.5, group="Excitability"),
        ],
        ScoringConsts(None, frozenset()),
    )
    assert result.domains[0].score is None
    assert result.domains[0].answered == 0


def test_score_session_without_consts_skips_only_other(db: Session) -> None:
    assert score_session(db, [_answer(1, 1, group="other")]) is None
    scored = score_session(db, [_answer(1, 2, group="Excitability")])
    assert scored is not None
    assert scored.domains[0].score == 2.0


def test_answer_rates_uses_latest_event_and_skips_missing(db: Session) -> None:
    owner = Owner(name="Владелец процента")
    dog = Dog(name="Percent Dog")
    empty_dog = Dog(name="Empty Percent Dog")
    survey = Survey(name="Percent Survey", slug=f"percent-{random_lower_string()}")
    scale = Scale(name="Балл", type="integer", config={"min_value": 0, "max_value": 4})
    db.add(owner)
    db.add(dog)
    db.add(empty_dog)
    db.add(survey)
    db.add(scale)
    db.commit()
    db.refresh(owner)
    db.refresh(dog)
    db.refresh(empty_dog)
    db.refresh(survey)
    db.refresh(scale)
    version = SurveyVersion(survey_id=survey.id, version_num=1)
    empty_version = SurveyVersion(survey_id=survey.id, version_num=2)
    db.add(version)
    db.add(empty_version)
    db.commit()
    db.refresh(version)
    db.refresh(empty_version)
    first = Question(text="Первый", scale_id=scale.id)
    second = Question(text="Второй", scale_id=scale.id)
    db.add(first)
    db.add(second)
    db.commit()
    db.refresh(first)
    db.refresh(second)
    db.add(
        SurveyQuestion(
            survey_version_id=version.id,
            question_id=first.id,
            order_num=1,
            display_num=1,
        )
    )
    db.add(
        SurveyQuestion(
            survey_version_id=version.id,
            question_id=second.id,
            order_num=2,
            display_num=2,
        )
    )
    answered = SurveySession(
        owner_id=owner.id,
        dog_id=dog.id,
        survey_version_id=version.id,
        status="draft",
    )
    empty = SurveySession(
        owner_id=owner.id,
        dog_id=empty_dog.id,
        survey_version_id=empty_version.id,
        status="draft",
    )
    db.add(answered)
    db.add(empty)
    db.commit()
    db.refresh(answered)
    db.refresh(empty)
    db.add(
        AnswerEvent(
            surveys_session_id=answered.id,
            survey_version_id=version.id,
            question_id=first.id,
            value={"value": -999},
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
    )
    db.add(
        AnswerEvent(
            surveys_session_id=answered.id,
            survey_version_id=version.id,
            question_id=first.id,
            value={"value": 2},
            created_at=datetime(2026, 2, 1, tzinfo=UTC),
        )
    )
    db.add(
        AnswerEvent(
            surveys_session_id=answered.id,
            survey_version_id=version.id,
            question_id=second.id,
            value={"value": 3},
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
    )
    db.add(
        AnswerEvent(
            surveys_session_id=answered.id,
            survey_version_id=version.id,
            question_id=second.id,
            value={"value": -999},
            created_at=datetime(2026, 2, 1, tzinfo=UTC),
        )
    )
    db.commit()
    rates = answer_rates(db, [answered.id, empty.id])
    assert rates[answered.id] == 50
    assert rates[empty.id] is None
    assert answer_rates(db, []) == {}


def test_answer_rates_counts_bare_json_numbers(db: Session) -> None:
    owner = Owner(name="Владелец скалярных ответов")
    dog = Dog(name="Scalar Percent Dog")
    survey = Survey(name="Scalar Percent", slug=f"scalar-{random_lower_string()}")
    scale = Scale(
        name="Балл скаляр", type="integer", config={"min_value": 0, "max_value": 4}
    )
    db.add(owner)
    db.add(dog)
    db.add(survey)
    db.add(scale)
    db.commit()
    db.refresh(owner)
    db.refresh(dog)
    db.refresh(survey)
    db.refresh(scale)
    version = SurveyVersion(survey_id=survey.id, version_num=1)
    db.add(version)
    db.commit()
    db.refresh(version)
    questions = []
    for order, question_text in enumerate(
        ("Первый", "Второй", "Третий", "Четвертый"), start=1
    ):
        question = Question(text=question_text, scale_id=scale.id)
        db.add(question)
        db.commit()
        db.refresh(question)
        db.add(
            SurveyQuestion(
                survey_version_id=version.id,
                question_id=question.id,
                order_num=order,
                display_num=order,
            )
        )
        questions.append(question)
    session_row = SurveySession(
        owner_id=owner.id,
        dog_id=dog.id,
        survey_version_id=version.id,
        status="draft",
    )
    db.add(session_row)
    db.commit()
    db.refresh(session_row)
    first, second, third, _fourth = questions

    def insert_event(question: Question, raw: str, created_at: datetime) -> None:
        db.execute(
            text(
                """
                INSERT INTO answer_events (
                    surveys_session_id,
                    survey_version_id,
                    question_id,
                    value,
                    created_at
                )
                VALUES (
                    :session_id,
                    :version_id,
                    :question_id,
                    CAST(:raw AS jsonb),
                    :created_at
                )
                """
            ),
            {
                "session_id": session_row.id,
                "version_id": version.id,
                "question_id": question.id,
                "raw": raw,
                "created_at": created_at,
            },
        )

    insert_event(first, "-999", datetime(2026, 1, 1, tzinfo=UTC))
    insert_event(first, "1", datetime(2026, 2, 1, tzinfo=UTC))
    insert_event(second, "4", datetime(2026, 1, 1, tzinfo=UTC))
    insert_event(second, "-999", datetime(2026, 2, 1, tzinfo=UTC))
    insert_event(third, '{"value": 2}', datetime(2026, 3, 1, tzinfo=UTC))
    db.commit()
    rates = answer_rates(db, [session_row.id])
    assert rates[session_row.id] == 50
