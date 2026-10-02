import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from app import crud
from app.core.config import settings
from app.models import (
    Dog,
    Owner,
    Recommendation,
    SessionRecommendation,
    Survey,
    SurveySession,
    SurveyVersion,
)
from tests.utils.utils import random_lower_string


def test_recommendation_persists_guid_and_text(db: Session) -> None:
    slug = f"rec-{random_lower_string()}"
    row = Recommendation(
        name="Тихий заход домой",
        slug=slug,
        text="Не устраивайте бурную встречу у двери.",
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    assert row.id is not None
    assert row.slug == slug
    assert row.created_at is not None
    assert row.updated_at is not None


def _session_recommendation_deps(db: Session) -> tuple:
    user = crud.get_user_by_email(session=db, email=settings.FIRST_SUPERUSER)
    assert user
    owner = Owner(name="Session Rec Owner")
    dog = Dog(name="Session Rec Dog")
    questionnaire = Survey(name="C-BARQ", slug=f"session-rec-{random_lower_string()}")
    recommendation = Recommendation(
        name="Прогулка",
        slug=f"leash-{random_lower_string()}",
        text="Короткие прогулки.",
    )
    db.add(owner)
    db.add(dog)
    db.add(questionnaire)
    db.add(recommendation)
    db.commit()
    db.refresh(dog)
    db.refresh(questionnaire)
    db.refresh(recommendation)
    version = SurveyVersion(
        survey_id=questionnaire.id,
        version_num=1,
        description=questionnaire.description,
    )
    db.add(version)
    db.commit()
    db.refresh(version)

    session_row = SurveySession(
        owner_id=owner.id,
        dog_id=dog.id,
        survey_version_id=version.id,
        status="draft",
    )
    db.add(session_row)
    db.commit()
    db.refresh(session_row)
    return user, dog, questionnaire, recommendation, session_row


def test_session_recommendation_persists_fields(db: Session) -> None:
    user, dog, questionnaire, recommendation, session_row = (
        _session_recommendation_deps(db)
    )

    row = SessionRecommendation(
        user_id=user.id,
        session_id=session_row.id,
        recomendation_id=recommendation.id,
        chart_number=2,
        weight=0.75,
        comment="высокий приоритет",
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    assert row.user_id == user.id
    assert row.session_id == session_row.id
    assert row.recomendation_id == recommendation.id
    assert row.chart_number == 2
    assert row.weight == 0.75
    assert row.comment == "высокий приоритет"
    assert row.created_at is not None
    assert row.updated_at is not None


def test_session_recommendation_unique_user_session_recomendation(
    db: Session,
) -> None:
    user, dog, questionnaire, recommendation, session_row = (
        _session_recommendation_deps(db)
    )

    db.add(
        SessionRecommendation(
            user_id=user.id,
            session_id=session_row.id,
            recomendation_id=recommendation.id,
            chart_number=1,
            weight=0.5,
        )
    )
    db.commit()

    db.add(
        SessionRecommendation(
            user_id=user.id,
            session_id=session_row.id,
            recomendation_id=recommendation.id,
            chart_number=3,
            weight=0.1,
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
