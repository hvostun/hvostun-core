from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.admin.deps import COOKIE_NAME
from app.core.config import settings
from app.models import (
    AnswerEvent,
    Dog,
    Owner,
    Question,
    Recommendation,
    Scale,
    SessionRecommendation,
    Shelter,
    Survey,
    SurveyQuestion,
    SurveySession,
    SurveyVersion,
    User,
)
from tests.utils.utils import random_lower_string


def test_login_page_is_html(client: TestClient) -> None:
    response = client.get("/login")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Войти" in response.text


def test_dogs_redirects_without_cookie(client: TestClient) -> None:
    response = client.get("/dogs", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_login_sets_cookie_and_opens_dogs(client: TestClient) -> None:
    response = client.post(
        "/login",
        data={
            "email": settings.FIRST_SUPERUSER,
            "password": settings.FIRST_SUPERUSER_PASSWORD,
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert COOKIE_NAME in response.cookies
    dogs = client.get("/dogs")
    assert dogs.status_code == 200
    assert "Собаки" in dogs.text
    assert "Владелец" in dogs.text
    assert "Приют" in dogs.text
    assert "owner_id" not in dogs.text
    assert "shelter_id" not in dogs.text


def test_dogs_page_shows_owner_name(client: TestClient, db: Session) -> None:
    owner = Owner(name="Teacher")
    shelter = Shelter(name="Приют Север")
    db.add(owner)
    db.add(shelter)
    db.commit()
    db.refresh(owner)
    db.refresh(shelter)
    dog = Dog(name="Rex", owner_id=owner.id, shelter_id=shelter.id)
    db.add(dog)
    db.commit()
    client.post(
        "/login",
        data={
            "email": settings.FIRST_SUPERUSER,
            "password": settings.FIRST_SUPERUSER_PASSWORD,
        },
    )
    dogs = client.get("/dogs")
    assert dogs.status_code == 200
    assert "Teacher" in dogs.text
    assert "Приют Север" in dogs.text
    assert str(dog.id) not in dogs.text
    assert str(owner.id) not in dogs.text
    assert str(shelter.id) not in dogs.text
    db.delete(dog)
    db.delete(owner)
    db.delete(shelter)
    db.commit()


def test_sessions_page_shows_related_names(client: TestClient, db: Session) -> None:
    user = db.exec(select(User).where(User.email == settings.FIRST_SUPERUSER)).first()
    assert user
    dog = Dog(name="Rex Sessions")
    survey = Survey(name="C-BARQ Sessions", slug="cbarq-sessions-admin")
    db.add(dog)
    db.add(survey)
    db.commit()
    db.refresh(dog)
    db.refresh(survey)
    version = SurveyVersion(
        survey_id=survey.id, version_num=1, description=survey.description
    )
    db.add(version)
    db.commit()
    db.refresh(version)
    session_row = SurveySession(
        owner_id=user.id,
        dog_id=dog.id,
        survey_version_id=version.id,
        status="draft",
    )
    db.add(session_row)
    db.commit()
    db.refresh(session_row)
    client.post(
        "/login",
        data={
            "email": settings.FIRST_SUPERUSER,
            "password": settings.FIRST_SUPERUSER_PASSWORD,
        },
    )
    sessions = client.get("/sessions")
    assert sessions.status_code == 200
    assert "Пользователь" in sessions.text
    assert "Собака" in sessions.text
    assert "Анкета" in sessions.text
    assert (user.full_name or user.email) in sessions.text
    assert "Rex Sessions" in sessions.text
    assert "C-BARQ Sessions" in sessions.text
    assert str(session_row.id) in sessions.text
    assert str(user.id) not in sessions.text
    assert str(dog.id) not in sessions.text
    assert str(survey.id) not in sessions.text


def test_session_detail_shows_scale_legend(client: TestClient, db: Session) -> None:
    user = db.exec(select(User).where(User.email == settings.FIRST_SUPERUSER)).first()
    assert user
    dog = Dog(name="Legend Dog")
    survey = Survey(name="Legend Survey", slug="legend-session-admin")
    scale = Scale(
        name="Частота",
        type="integer",
        config={
            "min_value": -1,
            "max_value": 4,
            "legend": {
                "0": "Нет, никогда",
                "1": "Редко",
                "3": "Обычно",
            },
        },
    )
    db.add(dog)
    db.add(survey)
    db.add(scale)
    db.commit()
    db.refresh(dog)
    db.refresh(survey)
    db.refresh(scale)
    version = SurveyVersion(
        survey_id=survey.id, version_num=1, description=survey.description
    )
    db.add(version)
    db.commit()
    db.refresh(version)
    question = Question(text="Как часто лает?", scale_id=scale.id)
    db.add(question)
    db.commit()
    db.refresh(question)
    link = SurveyQuestion(
        survey_version_id=version.id,
        question_id=question.id,
        order_num=1,
    )
    db.add(link)
    session_row = SurveySession(
        owner_id=user.id,
        dog_id=dog.id,
        survey_version_id=version.id,
        status="draft",
    )
    db.add(session_row)
    db.commit()
    db.refresh(session_row)
    event = AnswerEvent(
        surveys_session_id=session_row.id,
        survey_version_id=version.id,
        question_id=question.id,
        value={"value": 3},
    )
    db.add(event)
    db.commit()
    client.post(
        "/login",
        data={
            "email": settings.FIRST_SUPERUSER,
            "password": settings.FIRST_SUPERUSER_PASSWORD,
        },
    )
    page = client.get(f"/sessions/{session_row.id}")
    assert page.status_code == 200
    assert "Как часто лает?" in page.text
    assert "Обычно" in page.text
    assert "Значение" in page.text
    assert "№" in page.text
    assert "<td>1</td>" in page.text


def test_answer_events_page_is_visible_to_logged_in_user(
    client: TestClient, db: Session
) -> None:
    user = db.exec(select(User).where(User.email == settings.FIRST_SUPERUSER)).first()
    assert user
    dog = Dog(name="Answer Event Dog")
    survey = Survey(name="Answer Event Survey", slug="answer-events-admin")
    scale = Scale(
        name="Тест",
        type="integer",
        config={"min_value": 0, "max_value": 4},
    )
    db.add(dog)
    db.add(survey)
    db.add(scale)
    db.commit()
    db.refresh(dog)
    db.refresh(survey)
    db.refresh(scale)
    version = SurveyVersion(survey_id=survey.id, version_num=1)
    question = Question(text="Вопрос события", scale_id=scale.id)
    db.add(version)
    db.add(question)
    db.commit()
    db.refresh(version)
    db.refresh(question)
    db.add(
        SurveyQuestion(
            survey_version_id=version.id,
            question_id=question.id,
            order_num=1,
        )
    )
    session_row = SurveySession(
        owner_id=user.id,
        dog_id=dog.id,
        survey_version_id=version.id,
        status="draft",
    )
    db.add(session_row)
    db.commit()
    db.refresh(session_row)
    event = AnswerEvent(
        surveys_session_id=session_row.id,
        survey_version_id=version.id,
        question_id=question.id,
        value={"value": 1},
    )
    db.add(event)
    db.commit()
    client.post(
        "/login",
        data={
            "email": settings.FIRST_SUPERUSER,
            "password": settings.FIRST_SUPERUSER_PASSWORD,
        },
    )
    page = client.get("/answer-events")
    assert page.status_code == 200
    assert "События ответов" in page.text
    assert str(event.id) in page.text


def test_users_page_shows_group(client: TestClient) -> None:
    client.post(
        "/login",
        data={
            "email": settings.FIRST_SUPERUSER,
            "password": settings.FIRST_SUPERUSER_PASSWORD,
        },
    )
    page = client.get("/users")
    assert page.status_code == 200
    assert ">group<" in page.text
    assert "expert" in page.text


def _login_superuser(client: TestClient) -> None:
    client.post(
        "/login",
        data={
            "email": settings.FIRST_SUPERUSER,
            "password": settings.FIRST_SUPERUSER_PASSWORD,
        },
    )


def _session_with_recommendation_catalog(
    db: Session,
) -> tuple[SurveySession, Recommendation, User]:
    user = db.exec(select(User).where(User.email == settings.FIRST_SUPERUSER)).first()
    assert user
    dog = Dog(name="Rec Form Dog")
    survey = Survey(name="Rec Form Survey", slug=f"rec-form-{random_lower_string()}")
    recommendation = Recommendation(
        name="Короткая прогулка",
        slug=f"short-walk-{random_lower_string()}",
        text="Выходите на 10 минут.",
    )
    db.add(dog)
    db.add(survey)
    db.add(recommendation)
    db.commit()
    db.refresh(dog)
    db.refresh(survey)
    db.refresh(recommendation)
    version = SurveyVersion(survey_id=survey.id, version_num=1)
    db.add(version)
    db.commit()
    db.refresh(version)
    session_row = SurveySession(
        owner_id=user.id,
        dog_id=dog.id,
        survey_version_id=version.id,
        status="draft",
    )
    db.add(session_row)
    db.commit()
    db.refresh(session_row)
    return session_row, recommendation, user


def test_session_detail_can_add_recommendation(client: TestClient, db: Session) -> None:
    session_row, recommendation, user = _session_with_recommendation_catalog(db)
    _login_superuser(client)
    page = client.get(f"/sessions/{session_row.id}")
    assert page.status_code == 200
    assert "Добавить рекомендацию" in page.text
    assert recommendation.name in page.text

    response = client.post(
        f"/sessions/{session_row.id}/recommendations",
        data={
            "recomendation_id": str(recommendation.id),
            "comment": "приоритет на первую неделю",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == f"/sessions/{session_row.id}"

    saved = db.exec(
        select(SessionRecommendation).where(
            SessionRecommendation.session_id == session_row.id
        )
    ).first()
    assert saved is not None
    assert saved.user_id == user.id
    assert saved.recomendation_id == recommendation.id
    assert saved.comment == "приоритет на первую неделю"

    detail = client.get(f"/sessions/{session_row.id}")
    assert detail.status_code == 200
    assert "Короткая прогулка" in detail.text
    assert "приоритет на первую неделю" in detail.text
    assert str(user.id) in detail.text
    assert "Нет доступных рекомендаций для добавления." in detail.text


def test_session_recommendation_rejects_duplicate(
    client: TestClient, db: Session
) -> None:
    session_row, recommendation, user = _session_with_recommendation_catalog(db)
    db.add(
        SessionRecommendation(
            user_id=user.id,
            session_id=session_row.id,
            recomendation_id=recommendation.id,
            chart_number=0,
            weight=1.0,
        )
    )
    db.commit()
    _login_superuser(client)
    response = client.post(
        f"/sessions/{session_row.id}/recommendations",
        data={"recomendation_id": str(recommendation.id), "comment": ""},
    )
    assert response.status_code == 400
    assert "уже добавлена" in response.text


def test_json_api_is_gone(client: TestClient) -> None:
    response = client.get("/api/v1/surveys/")
    assert response.status_code == 404


def test_health_check(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
