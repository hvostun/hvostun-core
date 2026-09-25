import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session

from app import crud
from app.core.config import settings
from app.models import (
    AnswerEvent,
    Dog,
    Owner,
    Question,
    Recommendation,
    Scale,
    SessionRecommendation,
    Survey,
    SurveyQuestion,
    SurveySession,
    SurveyVersion,
)
from tests.utils.utils import random_email, random_lower_string


def test_read_dogs_as_normal_user(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    dog_name = f"List Dog {random_lower_string()}"
    dog = Dog(name=dog_name, status="shelter")
    db.add(dog)
    db.commit()

    r = client.get(f"{settings.API_V1_STR}/dogs/", headers=normal_user_token_headers)
    assert r.status_code == 200
    payload = r.json()
    assert payload["count"] >= 1
    assert any(item["name"] == dog_name for item in payload["data"])

    filtered = client.get(
        f"{settings.API_V1_STR}/dogs/",
        headers=normal_user_token_headers,
        params={"name": dog_name, "status": "shelter"},
    )
    assert filtered.status_code == 200
    assert filtered.json()["count"] >= 1
    assert all(item["status"] == "shelter" for item in filtered.json()["data"])


def test_read_owners_forbidden_for_normal_user(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    r = client.get(f"{settings.API_V1_STR}/owners/", headers=normal_user_token_headers)
    assert r.status_code == 403


def test_read_owners_as_superuser(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    owner_email = random_email()
    owner = Owner(name="Ivan Owner", email=owner_email, phone="123")
    db.add(owner)
    db.commit()

    r = client.get(f"{settings.API_V1_STR}/owners/", headers=superuser_token_headers)
    assert r.status_code == 200
    assert r.json()["count"] >= 1

    filtered = client.get(
        f"{settings.API_V1_STR}/owners/",
        headers=superuser_token_headers,
        params={"name": "Ivan", "email": owner_email, "phone": "123"},
    )
    assert filtered.status_code == 200
    assert filtered.json()["count"] >= 1
    assert all("Ivan" in item["name"] for item in filtered.json()["data"])


def test_read_recommendations_forbidden_for_normal_user(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    r = client.get(
        f"{settings.API_V1_STR}/recommendations/",
        headers=normal_user_token_headers,
    )
    assert r.status_code == 403


def test_read_recommendations_as_superuser(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    slug = f"leash-{random_lower_string()}"
    recommendation = Recommendation(
        name="Прогулка на поводке",
        slug=slug,
        text="Начинайте с коротких прогулок в спокойном месте.",
        description="адаптация",
    )
    db.add(recommendation)
    db.commit()

    r = client.get(
        f"{settings.API_V1_STR}/recommendations/",
        headers=superuser_token_headers,
    )
    assert r.status_code == 200
    payload = r.json()
    assert payload["count"] >= 1
    assert any(item["slug"] == slug for item in payload["data"])

    filtered = client.get(
        f"{settings.API_V1_STR}/recommendations/",
        headers=superuser_token_headers,
        params={"name": "поводке", "slug": slug},
    )
    assert filtered.status_code == 200
    assert filtered.json()["count"] >= 1
    assert all(slug in item["slug"] for item in filtered.json()["data"])


def test_read_questionnaires_as_normal_user(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    name = f"C-BARQ {random_lower_string()}"
    slug = f"cbarq-{random_lower_string()}"
    questionnaire = Survey(name=name, slug=slug, description="short")
    db.add(questionnaire)
    db.commit()

    r = client.get(
        f"{settings.API_V1_STR}/surveys/",
        headers=normal_user_token_headers,
    )
    assert r.status_code == 200
    payload = r.json()
    assert payload["count"] >= 1
    assert any(item["slug"] == slug for item in payload["data"])

    filtered = client.get(
        f"{settings.API_V1_STR}/surveys/",
        headers=normal_user_token_headers,
        params={"name": "C-BARQ", "slug": slug},
    )
    assert filtered.status_code == 200
    assert filtered.json()["count"] >= 1
    assert all(slug in item["slug"] for item in filtered.json()["data"])

    db.delete(questionnaire)
    db.commit()


def test_read_questionnaire_questions_as_normal_user(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    questionnaire = Survey(
        name="Questions Form", slug=f"questions-{random_lower_string()}"
    )
    scale = Scale(
        name="Тест",
        type="integer",
        config={"min_value": 0, "max_value": 4},
    )
    db.add(questionnaire)
    db.add(scale)
    db.commit()
    db.refresh(questionnaire)
    db.refresh(scale)
    version = SurveyVersion(
        survey_id=questionnaire.id,
        version_num=1,
        description=questionnaire.description,
    )
    db.add(version)
    db.commit()
    db.refresh(version)

    second = Question(
        global_id=uuid.uuid4(),
        text="Second question",
        scale_id=scale.id,
    )
    first = Question(
        global_id=uuid.uuid4(),
        text="First question",
        scale_id=scale.id,
    )
    db.add(second)
    db.add(first)
    db.commit()
    db.refresh(second)
    db.refresh(first)
    db.add(
        SurveyQuestion(
            survey_version_id=version.id,
            question_id=second.id,
            order_num=2,
        )
    )
    db.add(
        SurveyQuestion(
            survey_version_id=version.id,
            question_id=first.id,
            order_num=1,
        )
    )
    db.commit()

    detail = client.get(
        f"{settings.API_V1_STR}/surveys/{questionnaire.id}",
        headers=normal_user_token_headers,
    )
    assert detail.status_code == 200
    assert detail.json()["slug"] == questionnaire.slug

    questions = client.get(
        f"{settings.API_V1_STR}/surveys/versions/{version.id}/questions",
        headers=normal_user_token_headers,
    )
    assert questions.status_code == 200
    payload = questions.json()
    assert payload["count"] == 2
    assert [item["text"] for item in payload["data"]] == [
        "First question",
        "Second question",
    ]
    assert all(item["scale_name"] == "Тест" for item in payload["data"])

    missing = client.get(
        f"{settings.API_V1_STR}/surveys/versions/{uuid.uuid4()}/questions",
        headers=normal_user_token_headers,
    )
    assert missing.status_code == 404


def test_read_sessions_as_normal_user(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    user = crud.get_user_by_email(session=db, email=settings.EMAIL_TEST_USER)
    assert user
    dog = Dog(name="Session Dog")
    questionnaire = Survey(name="C-BARQ", slug=f"cbarq-list-{random_lower_string()}")
    db.add(dog)
    db.add(questionnaire)
    db.commit()
    db.refresh(dog)
    db.refresh(questionnaire)
    version = SurveyVersion(survey_id=questionnaire.id, version_num=1)
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

    r = client.get(
        f"{settings.API_V1_STR}/survey-sessions/",
        headers=normal_user_token_headers,
    )
    assert r.status_code == 200
    assert r.json()["count"] >= 1

    filtered = client.get(
        f"{settings.API_V1_STR}/survey-sessions/",
        headers=normal_user_token_headers,
        params={"status": "draft", "dog_id": str(dog.id)},
    )
    assert filtered.status_code == 200
    assert filtered.json()["count"] >= 1
    assert all(item["status"] == "draft" for item in filtered.json()["data"])


def test_read_session_detail_answers_and_recommendations(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    user = crud.get_user_by_email(session=db, email=settings.EMAIL_TEST_USER)
    admin = crud.get_user_by_email(session=db, email=settings.FIRST_SUPERUSER)
    assert user
    assert admin
    dog = Dog(name="Detail Session Dog")
    questionnaire = Survey(
        name="C-BARQ", slug=f"session-detail-{random_lower_string()}"
    )
    scale = Scale(
        name="Тест",
        type="integer",
        config={"min_value": 0, "max_value": 4},
    )
    catalog = Recommendation(
        name="Поводок",
        slug=f"leash-{random_lower_string()}",
        text="Короткие прогулки.",
    )
    db.add(dog)
    db.add(questionnaire)
    db.add(scale)
    db.add(catalog)
    db.commit()
    db.refresh(dog)
    db.refresh(questionnaire)
    db.refresh(scale)
    db.refresh(catalog)
    version = SurveyVersion(
        survey_id=questionnaire.id,
        version_num=1,
        description=questionnaire.description,
    )
    db.add(version)
    db.commit()
    db.refresh(version)

    q2 = Question(
        text="Второй вопрос",
        scale_id=scale.id,
    )
    q1 = Question(
        text="Первый вопрос",
        scale_id=scale.id,
    )
    db.add(q2)
    db.add(q1)
    db.commit()
    db.refresh(q1)
    db.refresh(q2)
    db.add(
        SurveyQuestion(
            survey_version_id=version.id,
            question_id=q2.id,
            order_num=2,
        )
    )
    db.add(
        SurveyQuestion(
            survey_version_id=version.id,
            question_id=q1.id,
            order_num=1,
        )
    )
    db.commit()

    session_row = SurveySession(
        owner_id=user.id,
        dog_id=dog.id,
        survey_version_id=version.id,
        status="draft",
    )
    db.add(session_row)
    db.commit()
    db.refresh(session_row)

    db.add(
        AnswerEvent(
            surveys_session_id=session_row.id,
            survey_version_id=version.id,
            question_id=q1.id,
            value={"value": 1},
        )
    )
    db.add(
        AnswerEvent(
            surveys_session_id=session_row.id,
            survey_version_id=version.id,
            question_id=q1.id,
            value={"value": 3},
        )
    )
    db.commit()

    rec_admin = SessionRecommendation(
        user_id=admin.id,
        session_id=session_row.id,
        recomendation_id=catalog.id,
        chart_number=1,
        weight=0.2,
        comment="admin",
    )
    rec_user = SessionRecommendation(
        user_id=user.id,
        session_id=session_row.id,
        recomendation_id=catalog.id,
        chart_number=5,
        weight=0.9,
        comment="user",
    )
    db.add(rec_admin)
    db.add(rec_user)
    db.commit()

    missing = client.get(
        f"{settings.API_V1_STR}/survey-sessions/{uuid.uuid4()}",
        headers=normal_user_token_headers,
    )
    assert missing.status_code == 404

    detail = client.get(
        f"{settings.API_V1_STR}/survey-sessions/{session_row.id}",
        headers=normal_user_token_headers,
    )
    assert detail.status_code == 200
    assert detail.json()["id"] == str(session_row.id)

    answers = client.get(
        f"{settings.API_V1_STR}/survey-sessions/{session_row.id}/answers",
        headers=normal_user_token_headers,
    )
    assert answers.status_code == 200
    items = answers.json()["data"]
    assert [item["question_text"] for item in items] == [
        "Первый вопрос",
        "Второй вопрос",
    ]
    assert items[0]["value"] == {"value": 3}
    assert items[1]["value"] is None

    recs = client.get(
        f"{settings.API_V1_STR}/survey-sessions/{session_row.id}/recommendations",
        headers=normal_user_token_headers,
    )
    assert recs.status_code == 200
    rec_items = recs.json()["data"]
    expected = sorted(
        (rec_admin, rec_user),
        key=lambda row: (row.user_id, row.chart_number),
    )
    assert [item["comment"] for item in rec_items] == [row.comment for row in expected]
    assert [item["user_id"] for item in rec_items] == [
        str(row.user_id) for row in expected
    ]
    assert rec_items[0]["recommendation_name"] == "Поводок"


def test_read_users_filters(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    r = client.get(
        f"{settings.API_V1_STR}/users/",
        headers=superuser_token_headers,
        params={"is_superuser": True, "limit": 50},
    )
    assert r.status_code == 200
    payload = r.json()
    assert payload["count"] >= 1
    assert all(item["is_superuser"] is True for item in payload["data"])
