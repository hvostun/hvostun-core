import uuid

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.core.config import settings
from app.models import (
    AnswerEvent,
    Dog,
    Owner,
    PlacementEvent,
    Question,
    Recommendation,
    Scale,
    Survey,
    SurveyQuestion,
    SurveySession,
    SurveyVersion,
    User,
)
from app.models.catalog_immutability import (
    CatalogImmutableError,
    DomainValueValidationError,
    JSONBValidationError,
)
from app.services import catalog as catalog_service
from tests.utils.utils import random_lower_string


def _admin(db: Session) -> User:
    user = db.exec(select(User).where(User.email == settings.FIRST_SUPERUSER)).one()
    return user


def _owner_id(db: Session) -> uuid.UUID:
    owner = Owner(name="Survey session owner")
    db.add(owner)
    db.commit()
    db.refresh(owner)
    return owner.id


def _catalog(
    db: Session,
) -> tuple[
    User,
    Dog,
    Survey,
    SurveyVersion,
    Scale,
    Question,
    SurveyQuestion,
]:
    user = _admin(db)
    dog = Dog(name=f"Dog {random_lower_string()}")
    survey = Survey(name="Immutable survey", slug=f"immutable-{random_lower_string()}")
    scale = Scale(
        name="Integer scale",
        type="integer",
        config={
            "min_value": 0,
            "max_value": 4,
            "legend": {0: "Нет", 4: "Всегда"},
        },
    )
    db.add(dog)
    db.add(survey)
    db.add(scale)
    db.commit()
    version = SurveyVersion(survey_id=survey.id, version_num=1)
    question = Question(text="Immutable question", scale_id=scale.id)
    db.add(version)
    db.add(question)
    db.commit()
    link = SurveyQuestion(
        survey_version_id=version.id,
        question_id=question.id,
        order_num=1,
        user_id=user.id,
    )
    db.add(link)
    db.commit()
    return user, dog, survey, version, scale, question, link


def _session_with_answer(
    db: Session,
) -> tuple[SurveyVersion, Question, SurveySession, AnswerEvent]:
    _user, dog, _survey, version, _scale, question, _link = _catalog(db)
    row = SurveySession(
        owner_id=_owner_id(db),
        dog_id=dog.id,
        survey_version_id=version.id,
        status="draft",
    )
    db.add(row)
    db.commit()
    event = AnswerEvent(
        surveys_session_id=row.id,
        survey_version_id=version.id,
        question_id=question.id,
        value={"value": 4},
    )
    db.add(event)
    db.commit()
    return version, question, row, event


@pytest.mark.parametrize("entity_name", ["version", "question"])
def test_catalog_rows_are_immutable(db: Session, entity_name: str) -> None:
    _user, _dog, _survey, version, _scale, question, _link = _catalog(db)
    entity = {
        "version": version,
        "question": question,
    }[entity_name]
    if entity_name == "version":
        version.description = "changed"
    else:
        question.text = "changed"
    with pytest.raises(CatalogImmutableError):
        db.commit()
    db.rollback()

    db.delete(entity)
    with pytest.raises(CatalogImmutableError):
        db.commit()
    db.rollback()


def test_scale_can_be_updated_but_not_deleted(db: Session) -> None:
    _user, _dog, _survey, _version, scale, _question, _link = _catalog(db)
    scale.name = "changed scale"
    db.commit()
    db.refresh(scale)
    assert scale.name == "changed scale"

    db.delete(scale)
    with pytest.raises(CatalogImmutableError):
        db.commit()
    db.rollback()


def test_recommendation_can_be_updated_but_not_deleted(db: Session) -> None:
    recommendation = Recommendation(
        name="Immutable recommendation",
        slug=f"immutable-rec-{random_lower_string()}",
        text="Text",
    )
    db.add(recommendation)
    db.commit()
    recommendation.text = "Changed"
    db.commit()
    db.refresh(recommendation)
    assert recommendation.text == "Changed"
    db.delete(recommendation)
    with pytest.raises(CatalogImmutableError):
        db.commit()
    db.rollback()

    _version, _question, _row, event = _session_with_answer(db)
    event.value = {"value": 0}
    with pytest.raises(CatalogImmutableError):
        db.commit()
    db.rollback()
    db.delete(event)
    with pytest.raises(CatalogImmutableError):
        db.commit()
    db.rollback()


def test_version_composition_closes_after_first_session(db: Session) -> None:
    _user, dog, _survey, version, scale, _question, link = _catalog(db)
    second = Question(text="Second", scale_id=scale.id)
    db.add(second)
    db.commit()
    row = SurveySession(
        owner_id=_owner_id(db),
        dog_id=dog.id,
        survey_version_id=version.id,
    )
    db.add(row)
    db.commit()

    db.add(
        SurveyQuestion(
            survey_version_id=version.id,
            question_id=second.id,
            order_num=2,
        )
    )
    with pytest.raises(CatalogImmutableError):
        db.commit()
    db.rollback()

    link.order_num = 3
    with pytest.raises(CatalogImmutableError):
        db.commit()
    db.rollback()
    db.delete(link)
    with pytest.raises(CatalogImmutableError):
        db.commit()
    db.rollback()


def test_survey_question_group_and_display_num_can_change(db: Session) -> None:
    _user, dog, _survey, version, _scale, _question, link = _catalog(db)
    db.add(
        SurveySession(
            owner_id=_owner_id(db),
            dog_id=dog.id,
            survey_version_id=version.id,
        )
    )
    db.commit()
    link.group = "Custom"
    link.display_num = 4
    db.commit()
    db.refresh(link)
    assert link.group == "Custom"
    assert link.display_num == 4


def test_session_cannot_move_to_another_version(db: Session) -> None:
    _user, dog, survey, version, _scale, _question, _link = _catalog(db)
    row = SurveySession(
        owner_id=_owner_id(db),
        dog_id=dog.id,
        survey_version_id=version.id,
    )
    db.add(row)
    db.commit()
    other = SurveyVersion(survey_id=survey.id, version_num=2)
    db.add(other)
    db.commit()
    row.survey_version_id = other.id
    with pytest.raises(CatalogImmutableError):
        db.commit()
    db.rollback()


def test_new_version_has_independent_order_and_preserves_old_session(
    db: Session,
) -> None:
    user, dog, survey, version_one, scale, question, _link = _catalog(db)
    session_row = SurveySession(
        owner_id=_owner_id(db),
        dog_id=dog.id,
        survey_version_id=version_one.id,
    )
    second = Question(text="Version two only", scale_id=scale.id)
    db.add(session_row)
    db.add(second)
    db.commit()

    version_two = catalog_service.create_survey_version(
        db,
        survey_id=survey.id,
        description="Second version",
        questions=[(second.id, 1), (question.id, 2)],
        user_id=user.id,
    )
    rows_one = catalog_service.get_version_questions(db, version_one.id)
    rows_two = catalog_service.get_version_questions(db, version_two.id)

    assert session_row.survey_version_id == version_one.id
    assert [link.order_num for _, _, link in rows_one] == [1]
    assert [link.order_num for _, _, link in rows_two] == [1, 2]


@pytest.mark.parametrize(
    ("config", "valid"),
    [
        ({"min_value": 0, "max_value": 4}, True),
        ({"min_value": 4, "max_value": 0}, False),
        ({"min_value": 0, "max_value": 4, "extra": True}, False),
    ],
)
def test_scale_config_validation(
    db: Session, config: dict[str, object], valid: bool
) -> None:
    scale = Scale(
        name=f"Scale {random_lower_string()}",
        type="integer",
        config=config,
    )
    db.add(scale)
    if valid:
        db.commit()
    else:
        with pytest.raises(JSONBValidationError):
            db.commit()
        db.rollback()


@pytest.mark.parametrize(
    ("model", "field", "value"),
    [
        (Dog, "status", "invalid"),
        (SurveySession, "status", "invalid"),
        (Scale, "type", "invalid"),
        (PlacementEvent, "code", "unknown"),
        (User, "group", "invalid"),
        (Recommendation, "group", "Excitability"),
    ],
)
def test_domain_values_reject_invalid_assignments(
    db: Session, model: type[object], field: str, value: str
) -> None:
    if model is Dog:
        obj = Dog(name="Invalid")
    elif model is User:
        obj = User(
            email=f"{uuid.uuid4()}@example.com",
            hashed_password="not-a-real-hash",
        )
    elif model is Scale:
        obj = Scale(
            name="Invalid",
            type="integer",
            config={"min_value": 0, "max_value": 1},
        )
    elif model is PlacementEvent:
        dog = Dog(name="Placement dog")
        db.add(dog)
        db.commit()
        obj = PlacementEvent(dog_id=dog.id, code="shelter_started")
    elif model is Recommendation:
        obj = Recommendation(
            name="Invalid group",
            slug=f"invalid-group-{uuid.uuid4()}",
            text="text",
        )
    else:
        _user, dog, _survey, version, _scale, _question, _link = _catalog(db)
        obj = SurveySession(
            owner_id=_owner_id(db),
            dog_id=dog.id,
            survey_version_id=version.id,
        )
    setattr(obj, field, value)
    db.add(obj)
    with pytest.raises(DomainValueValidationError):
        db.commit()
    db.rollback()


def test_survey_question_accepts_any_group(db: Session) -> None:
    _user, _dog, _survey, version, _scale, question, _link = _catalog(db)
    extra = Question(text="Custom group question", scale_id=question.scale_id)
    db.add(extra)
    db.commit()
    link = SurveyQuestion(
        survey_version_id=version.id,
        question_id=extra.id,
        order_num=2,
        group="NotInDictionary",
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    assert link.group == "NotInDictionary"


def test_answer_composite_foreign_keys(db: Session) -> None:
    version, question, row, _event = _session_with_answer(db)
    other_survey = Survey(name="Other", slug=f"other-{random_lower_string()}")
    db.add(other_survey)
    db.commit()
    other_version = SurveyVersion(survey_id=other_survey.id, version_num=1)
    db.add(other_version)
    db.commit()
    invalid = AnswerEvent(
        surveys_session_id=row.id,
        survey_version_id=other_version.id,
        question_id=question.id,
        value={"value": 4},
    )
    db.add(invalid)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_dog_unknown_remains_allowed(db: Session) -> None:
    dog = Dog(name=f"Unknown {uuid.uuid4()}", status="unknown")
    db.add(dog)
    db.commit()
    assert dog.status == "unknown"
