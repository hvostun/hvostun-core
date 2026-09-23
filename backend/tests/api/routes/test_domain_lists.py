from fastapi.testclient import TestClient
from sqlmodel import Session

from app import crud
from app.core.config import settings
from app.models import Dog, Owner, Questionnaire, QuestionnaireSession
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


def test_read_sessions_as_normal_user(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    user = crud.get_user_by_email(session=db, email=settings.EMAIL_TEST_USER)
    assert user
    dog = Dog(name="Session Dog")
    questionnaire = Questionnaire(
        name="C-BARQ", slug=f"cbarq-list-{random_lower_string()}"
    )
    db.add(dog)
    db.add(questionnaire)
    db.commit()
    db.refresh(dog)
    db.refresh(questionnaire)

    session_row = QuestionnaireSession(
        user_id=user.id,
        dog_id=dog.id,
        questionnaire_id=questionnaire.id,
        status="draft",
    )
    db.add(session_row)
    db.commit()

    r = client.get(
        f"{settings.API_V1_STR}/questionnaire-sessions/",
        headers=normal_user_token_headers,
    )
    assert r.status_code == 200
    assert r.json()["count"] >= 1

    filtered = client.get(
        f"{settings.API_V1_STR}/questionnaire-sessions/",
        headers=normal_user_token_headers,
        params={"status": "draft", "dog_id": str(dog.id)},
    )
    assert filtered.status_code == 200
    assert filtered.json()["count"] >= 1
    assert all(item["status"] == "draft" for item in filtered.json()["data"])

    db.delete(session_row)
    db.commit()
    db.delete(questionnaire)
    db.delete(dog)
    db.commit()


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
