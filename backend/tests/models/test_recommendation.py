import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app import crud
from app.core.config import settings
from app.models import (
    Dog,
    Questionnaire,
    QuestionnaireSession,
    Recommendation,
    SessionRecommendation,
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

    db.delete(row)
    db.commit()


def _session_recommendation_deps(db: Session) -> tuple:
    user = crud.get_user_by_email(session=db, email=settings.FIRST_SUPERUSER)
    assert user
    dog = Dog(name="Session Rec Dog")
    questionnaire = Questionnaire(
        name="C-BARQ", slug=f"session-rec-{random_lower_string()}"
    )
    recommendation = Recommendation(
        name="Прогулка",
        slug=f"leash-{random_lower_string()}",
        text="Короткие прогулки.",
    )
    db.add(dog)
    db.add(questionnaire)
    db.add(recommendation)
    db.commit()
    db.refresh(dog)
    db.refresh(questionnaire)
    db.refresh(recommendation)

    session_row = QuestionnaireSession(
        user_id=user.id,
        dog_id=dog.id,
        questionnaire_id=questionnaire.id,
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

    db.delete(row)
    db.commit()
    db.delete(session_row)
    db.commit()
    db.delete(recommendation)
    db.delete(questionnaire)
    db.delete(dog)
    db.commit()


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

    for item in db.exec(
        select(SessionRecommendation).where(
            SessionRecommendation.session_id == session_row.id
        )
    ).all():
        db.delete(item)
    db.commit()
    db.delete(session_row)
    db.commit()
    db.delete(recommendation)
    db.delete(questionnaire)
    db.delete(dog)
    db.commit()
