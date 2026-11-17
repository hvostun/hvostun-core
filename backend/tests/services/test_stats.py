from datetime import UTC, datetime

from sqlmodel import Session

from app import crud
from app.models import (
    Dog,
    Owner,
    Recommendation,
    SessionRecommendation,
    Survey,
    SurveySession,
    SurveyVersion,
    User,
    UserCreate,
    UserGroup,
)
from app.services.stats import ExpertTotals, expert_totals
from tests.utils.utils import random_lower_string


def _user(db: Session, group: UserGroup) -> User:
    return crud.create_user(
        session=db,
        user_create=UserCreate(
            email=f"totals-{random_lower_string()}@example.com",
            password=f"Stat1-{random_lower_string()[:8]}",
            group=group,
        ),
    )


def _session(db: Session) -> SurveySession:
    owner = Owner(name=f"Владелец {random_lower_string()}")
    dog = Dog(name=f"Пёс {random_lower_string()}")
    survey = Survey(name="Статистика", slug=f"totals-{random_lower_string()}")
    db.add(owner)
    db.add(dog)
    db.add(survey)
    db.commit()
    db.refresh(dog)
    db.refresh(survey)
    version = SurveyVersion(survey_id=survey.id, version_num=1)
    db.add(version)
    db.commit()
    db.refresh(version)
    row = SurveySession(
        owner_id=owner.id,
        dog_id=dog.id,
        survey_version_id=version.id,
        status="draft",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _assign(
    db: Session, user: User, session_row: SurveySession, when: datetime
) -> None:
    recommendation = Recommendation(
        name="Рекомендация",
        slug=f"totals-rec-{random_lower_string()}",
        text="Текст",
    )
    db.add(recommendation)
    db.commit()
    db.refresh(recommendation)
    db.add(
        SessionRecommendation(
            user_id=user.id,
            session_id=session_row.id,
            recomendation_id=recommendation.id,
            chart_number=0,
            weight=1.0,
            created_at=when,
        )
    )
    db.commit()


def test_expert_totals_window_includes_every_author(db: Session) -> None:
    admin = _user(db, UserGroup.ADMIN)
    expert = _user(db, UserGroup.EXPERT)
    inside = _session(db)
    outside = _session(db)
    before = expert_totals(db)
    _assign(db, admin, inside, datetime(1999, 6, 1, 12, tzinfo=UTC))
    _assign(db, expert, inside, datetime(1999, 6, 1, 18, tzinfo=UTC))
    _assign(db, admin, outside, datetime(1999, 5, 1, 12, tzinfo=UTC))

    after = expert_totals(db)
    assert after == ExpertTotals(
        surveys=before.surveys + 2,
        evaluations=before.evaluations + 3,
        recommendations=before.recommendations + 3,
    )
    window = expert_totals(
        db,
        since=datetime(1999, 6, 1, tzinfo=UTC),
        until=datetime(1999, 6, 2, tzinfo=UTC),
    )
    assert window == ExpertTotals(surveys=1, evaluations=2, recommendations=2)
