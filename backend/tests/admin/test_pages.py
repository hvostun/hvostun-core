import re
import uuid
from datetime import UTC, date, datetime
from typing import Any

from fastapi.testclient import TestClient
from httpx import Response
from sqlmodel import Session, select

from app import crud
from app.admin.deps import COOKIE_NAME, CSRF_COOKIE_NAME
from app.core.config import settings
from app.models import (
    AnswerEvent,
    Dictionary,
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
    UserCreate,
    UserGroup,
)
from app.services.dictionaries import (
    SURVEYS_QUESTIONS_CONSTS_KEY,
    SURVEYS_QUESTIONS_GROUP_KEY,
)
from app.services.sessions import (
    days_since_status,
    format_dog_age,
    session_calendar_date,
)
from tests.utils.utils import random_lower_string


def post(
    client: TestClient,
    url: str,
    data: dict[str, str] | None = None,
    **kwargs: Any,
) -> Response:
    if CSRF_COOKIE_NAME not in client.cookies:
        client.get("/login")
    payload: dict[str, str] = {"csrf_token": client.cookies[CSRF_COOKIE_NAME]}
    if data:
        payload.update(data)
    return client.post(url, data=payload, **kwargs)


def test_login_page_is_html(client: TestClient) -> None:
    response = client.get("/login")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Войти" in response.text
    assert 'name="csrf_token"' in response.text
    assert CSRF_COOKIE_NAME in client.cookies
    assert "/static/theme.css" in response.text
    theme = client.get("/static/theme.css")
    assert theme.status_code == 200
    assert "--primary:" in theme.text
    assert "--bs-primary:" in theme.text


def test_dogs_redirects_without_cookie(client: TestClient) -> None:
    response = client.get("/dogs", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_login_sets_cookie_and_opens_dogs(client: TestClient) -> None:
    response = post(
        client,
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
    post(
        client,
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
    assert f"/dogs/{dog.id}" in dogs.text
    assert str(owner.id) not in dogs.text
    assert str(shelter.id) not in dogs.text
    db.delete(dog)
    db.delete(owner)
    db.delete(shelter)
    db.commit()


def test_dog_detail_shows_edit_form(client: TestClient, db: Session) -> None:
    owner = Owner(name="Edit Owner")
    shelter = Shelter(name="Приют Юг")
    db.add(owner)
    db.add(shelter)
    db.commit()
    db.refresh(owner)
    db.refresh(shelter)
    dog = Dog(
        name="Edit Dog",
        sex="female",
        breed="метис",
        status="home",
        owner_id=owner.id,
        shelter_id=shelter.id,
        birthday=date(2024, 6, 20),
        status_at=date(2026, 9, 10),
    )
    db.add(dog)
    db.commit()
    db.refresh(dog)
    _login_superuser(client)
    page = client.get(f"/dogs/{dog.id}")
    assert page.status_code == 200
    assert "Edit Dog" in page.text
    assert "Сохранить" in page.text
    assert "Приют Юг" in page.text
    assert "Edit Owner" in page.text
    assert 'name="status_at"' in page.text
    missing = client.get(f"/dogs/{uuid.uuid4()}")
    assert missing.status_code == 404


def test_dog_update_saves_fields(client: TestClient, db: Session) -> None:
    owner = Owner(name="New Owner")
    shelter = Shelter(name="Новый приют")
    db.add(owner)
    db.add(shelter)
    db.commit()
    db.refresh(owner)
    db.refresh(shelter)
    dog = Dog(name="Before", status="unknown")
    db.add(dog)
    db.commit()
    db.refresh(dog)
    _login_superuser(client)
    response = post(
        client,
        f"/dogs/{dog.id}",
        data={
            "name": "After",
            "sex": "male",
            "neutered": "true",
            "status": "shelter",
            "description": "после правки",
            "shelter_id": str(shelter.id),
            "assigned_volunteer_id": "",
            "owner_id": str(owner.id),
            "birthday": "2023-01-15",
            "status_at": "2026-09-01",
            "breed": "лабрадор",
            "mixed": "false",
            "weight": "10",
            "height": "50",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    db.refresh(dog)
    assert dog.name == "After"
    assert dog.sex == "male"
    assert dog.neutered is True
    assert dog.status == "shelter"
    assert dog.description == "после правки"
    assert dog.shelter_id == shelter.id
    assert dog.owner_id == owner.id
    assert dog.birthday == date(2023, 1, 15)
    assert dog.status_at == date(2026, 9, 1)
    assert dog.breed == "лабрадор"
    assert dog.mixed is False


def test_dog_update_rejects_empty_name(client: TestClient, db: Session) -> None:
    dog = Dog(name="Keep Name", status="unknown")
    db.add(dog)
    db.commit()
    db.refresh(dog)
    _login_superuser(client)
    response = post(
        client,
        f"/dogs/{dog.id}",
        data={
            "name": "   ",
            "sex": "",
            "neutered": "",
            "status": "unknown",
            "description": "",
            "shelter_id": "",
            "assigned_volunteer_id": "",
            "owner_id": "",
            "birthday": "",
            "status_at": "",
            "breed": "",
            "mixed": "",
        },
    )
    assert response.status_code == 400
    assert "Имя обязательно" in response.text
    db.refresh(dog)
    assert dog.name == "Keep Name"


def test_sessions_page_shows_related_names(client: TestClient, db: Session) -> None:
    user = db.exec(select(User).where(User.email == settings.FIRST_SUPERUSER)).first()
    assert user
    owner = Owner(name="Владелец сессии")
    dog = Dog(name="Rex Sessions")
    survey = Survey(name="C-BARQ Sessions", slug="cbarq-sessions-admin")
    db.add(owner)
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
        owner_id=owner.id,
        dog_id=dog.id,
        survey_version_id=version.id,
        status="draft",
    )
    db.add(session_row)
    db.commit()
    db.refresh(session_row)
    post(
        client,
        "/login",
        data={
            "email": settings.FIRST_SUPERUSER,
            "password": settings.FIRST_SUPERUSER_PASSWORD,
        },
    )
    sessions = client.get("/sessions")
    assert sessions.status_code == 200
    assert "Моя рекомендация" in sessions.text
    assert "Собака" in sessions.text
    assert "Анкета" in sessions.text
    assert "Рекомендации" in sessions.text
    assert "Пользователи" in sessions.text
    assert owner.name in sessions.text
    assert "Rex Sessions" in sessions.text
    assert "C-BARQ Sessions" in sessions.text
    assert str(session_row.id) in sessions.text
    assert str(user.id) not in sessions.text
    assert str(dog.id) not in sessions.text
    assert str(survey.id) not in sessions.text
    assert re.search(
        r"C-BARQ Sessions · v1\s*</td>\s*<td>\s*—\s*</td>\s*<td>\s*0\s*</td>\s*<td>\s*0\s*</td>",
        sessions.text,
    )


def test_sessions_page_shows_recommendation_counts(
    client: TestClient, db: Session
) -> None:
    owner = db.exec(select(User).where(User.email == settings.FIRST_SUPERUSER)).first()
    assert owner
    session_owner = Owner(name="Владелец рекомендаций")
    other = crud.create_user(
        session=db,
        user_create=UserCreate(
            email=f"rec-count-{random_lower_string()}@example.com",
            password=f"Pass1-{random_lower_string()[:8]}",
        ),
    )
    dog = Dog(name="Rex Rec Counts")
    survey = Survey(
        name="C-BARQ Rec Counts", slug=f"cbarq-rec-counts-{random_lower_string()}"
    )
    first = Recommendation(
        name="Первая",
        slug=f"first-{random_lower_string()}",
        text="Один.",
    )
    second = Recommendation(
        name="Вторая",
        slug=f"second-{random_lower_string()}",
        text="Два.",
    )
    db.add(session_owner)
    db.add(dog)
    db.add(survey)
    db.add(first)
    db.add(second)
    db.commit()
    db.refresh(dog)
    db.refresh(survey)
    db.refresh(first)
    db.refresh(second)
    version = SurveyVersion(
        survey_id=survey.id, version_num=1, description=survey.description
    )
    db.add(version)
    db.commit()
    db.refresh(version)
    session_row = SurveySession(
        owner_id=session_owner.id,
        dog_id=dog.id,
        survey_version_id=version.id,
        status="draft",
    )
    db.add(session_row)
    db.commit()
    db.refresh(session_row)
    db.add(
        SessionRecommendation(
            user_id=owner.id,
            session_id=session_row.id,
            recomendation_id=first.id,
            chart_number=0,
            weight=1.0,
        )
    )
    db.add(
        SessionRecommendation(
            user_id=owner.id,
            session_id=session_row.id,
            recomendation_id=second.id,
            chart_number=1,
            weight=0.5,
        )
    )
    db.add(
        SessionRecommendation(
            user_id=other.id,
            session_id=session_row.id,
            recomendation_id=first.id,
            chart_number=0,
            weight=1.0,
        )
    )
    db.commit()
    empty_dog = Dog(name="Rex Without Recommendations")
    empty_session = SurveySession(
        owner_id=session_owner.id,
        dog_id=empty_dog.id,
        survey_version_id=version.id,
        status="draft",
    )
    db.add(empty_dog)
    db.add(empty_session)
    db.commit()
    post(
        client,
        "/login",
        data={
            "email": settings.FIRST_SUPERUSER,
            "password": settings.FIRST_SUPERUSER_PASSWORD,
        },
    )
    sessions = client.get("/sessions", params={"mine": ""})
    assert sessions.status_code == 200
    assert "Rex Rec Counts" in sessions.text
    assert re.search(
        r"C-BARQ Rec Counts · v1\s*</td>\s*<td>\s*—\s*</td>\s*<td>\s*3\s*</td>\s*<td>\s*2\s*</td>",
        sessions.text,
    )
    assert 'name="has_my_recommendation"' not in sessions.text
    mine_row = re.search(r"Rex Rec Counts.*?</tr>", sessions.text, re.S)
    empty_row = re.search(r"Rex Without Recommendations.*?</tr>", sessions.text, re.S)
    assert mine_row is not None and "checked" in mine_row.group(0)
    assert empty_row is not None and "checked" not in empty_row.group(0)

    ascending = client.get("/sessions", params={"users_sort": "asc", "mine": ""})
    assert ascending.text.index("Rex Without Recommendations") < ascending.text.index(
        "Rex Rec Counts"
    )
    descending = client.get("/sessions", params={"users_sort": "desc", "mine": ""})
    assert descending.text.index("Rex Rec Counts") < descending.text.index(
        "Rex Without Recommendations"
    )
    assert 'name="mine"' in sessions.text
    assert "Мои рекомендации" in sessions.text
    assert "Без моей рекомендации" in sessions.text
    only_mine = client.get("/sessions", params={"mine": "yes"})
    assert "Rex Rec Counts" in only_mine.text
    assert "Rex Without Recommendations" not in only_mine.text
    assert 'value="yes" selected' in only_mine.text
    without_mine = client.get("/sessions", params={"mine": "no"})
    assert "Rex Without Recommendations" in without_mine.text
    assert "Rex Rec Counts" not in without_mine.text
    assert 'value="no" selected' in without_mine.text


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
    group_labels = {
        "other": {"name": "Прочее", "color": "var(--bs-blue)"},
        "Excitability": {"name": "Возбудимость", "color": "var(--bs-orange)"},
    }
    group_row = db.get(Dictionary, "surveys_questions::group")
    if group_row is None:
        db.add(
            Dictionary(
                key="surveys_questions::group",
                value=group_labels,
                created_by=user.id,
                updated_by=user.id,
            )
        )
    else:
        group_row.value = group_labels
        db.add(group_row)
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
        display_num=1,
        group="NotInDictionary",
    )
    db.add(link)
    session_row = SurveySession(
        owner_id=_create_owner(db).id,
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
    post(
        client,
        "/login",
        data={
            "email": settings.FIRST_SUPERUSER,
            "password": settings.FIRST_SUPERUSER_PASSWORD,
        },
    )
    page = client.get(f"/sessions/{session_row.id}", params={"view": "flat"})
    assert page.status_code == 200
    assert "Как часто лает?" in page.text
    assert "Категория" in page.text
    assert "NotInDictionary" in page.text
    assert "Прочее" in page.text
    assert 'value="other"' in page.text
    assert "Обычно" in page.text
    assert "progress-bar" in page.text
    assert "width: 75%" in page.text
    assert "var(--bs-blue)" in page.text
    assert "Значение" in page.text
    assert "<td>1</td>" in page.text
    assert "Все категории" in page.text
    assert "Все ответы" in page.text


def test_session_detail_hides_progress_for_missing_answer(
    client: TestClient, db: Session
) -> None:
    user = db.exec(select(User).where(User.email == settings.FIRST_SUPERUSER)).first()
    assert user
    dog = Dog(name="Missing Bar Dog")
    survey = Survey(
        name="Missing Bar Survey", slug=f"missing-bar-{random_lower_string()}"
    )
    scale = Scale(
        name="Балл",
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
    db.add(version)
    db.commit()
    db.refresh(version)
    question = Question(text="Не применимо?", scale_id=scale.id)
    db.add(question)
    db.commit()
    db.refresh(question)
    db.add(
        SurveyQuestion(
            survey_version_id=version.id,
            question_id=question.id,
            order_num=1,
            display_num=1,
            group="Aggression",
        )
    )
    session_row = SurveySession(
        owner_id=_create_owner(db).id,
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
            question_id=question.id,
            value={"value": -999},
        )
    )
    db.commit()
    _login_superuser(client)
    page = client.get(f"/sessions/{session_row.id}", params={"view": "flat"})
    assert page.status_code == 200
    assert "Не применимо?" in page.text
    assert "progress-bar" not in page.text
    assert "—" in page.text


def test_session_detail_filters_questions_by_category_and_answer(
    client: TestClient, db: Session
) -> None:
    user = db.exec(select(User).where(User.email == settings.FIRST_SUPERUSER)).first()
    assert user
    dog = Dog(name="Filter Dog")
    survey = Survey(name="Filter Survey", slug=f"filter-{random_lower_string()}")
    scale = Scale(
        name="Балл",
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
    db.add(version)
    db.commit()
    db.refresh(version)
    first = Question(text="Лает на гостей?", scale_id=scale.id)
    second = Question(text="Рычит на собак?", scale_id=scale.id)
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
            group="Excitability",
        )
    )
    db.add(
        SurveyQuestion(
            survey_version_id=version.id,
            question_id=second.id,
            order_num=2,
            display_num=2,
            group="Aggression",
        )
    )
    session_row = SurveySession(
        owner_id=_create_owner(db).id,
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
            question_id=first.id,
            value={"value": 3},
        )
    )
    db.commit()
    _login_superuser(client)
    page = client.get(f"/sessions/{session_row.id}", params={"view": "flat"})
    assert page.status_code == 200
    assert "Лает на гостей?" in page.text
    assert "Рычит на собак?" in page.text
    by_category = client.get(
        f"/sessions/{session_row.id}",
        params={"view": "flat", "category": "Excitability"},
    )
    assert by_category.status_code == 200
    assert "Лает на гостей?" in by_category.text
    assert "Рычит на собак?" not in by_category.text
    by_answer = client.get(
        f"/sessions/{session_row.id}", params={"view": "flat", "answer": "3"}
    )
    assert "Лает на гостей?" in by_answer.text
    assert "Рычит на собак?" not in by_answer.text
    unanswered = client.get(
        f"/sessions/{session_row.id}",
        params={"view": "flat", "answer": "unanswered"},
    )
    assert "Рычит на собак?" in unanswered.text
    assert "Лает на гостей?" not in unanswered.text
    empty = client.get(
        f"/sessions/{session_row.id}",
        params={"view": "flat", "category": "Aggression", "answer": "3"},
    )
    assert "Нет вопросов по фильтру." in empty.text
    assert "Лает на гостей?" not in empty.text


def test_session_detail_shows_dog_facts(client: TestClient, db: Session) -> None:
    user = db.exec(select(User).where(User.email == settings.FIRST_SUPERUSER)).first()
    assert user
    dog = Dog(
        name="Facts Dog",
        sex="female",
        breed="метис",
        status="home",
        birthday=date(2024, 6, 20),
        status_at=date(2026, 9, 10),
        weight=12.5,
        height=48,
        history="из приюта",
    )
    survey = Survey(name="Facts Survey", slug=f"facts-{random_lower_string()}")
    db.add(
        Dictionary(
            key="dogs::sex",
            value={"female": "сука", "male": "кобель"},
            created_by=user.id,
            updated_by=user.id,
        )
    )
    db.add(
        Dictionary(
            key="dogs::status",
            value={"home": "дома", "shelter": "приют"},
            created_by=user.id,
            updated_by=user.id,
        )
    )
    db.add(dog)
    db.add(survey)
    db.commit()
    db.refresh(dog)
    db.refresh(survey)
    version = SurveyVersion(survey_id=survey.id, version_num=1)
    db.add(version)
    db.commit()
    db.refresh(version)
    session_row = SurveySession(
        owner_id=_create_owner(db).id,
        dog_id=dog.id,
        survey_version_id=version.id,
        status="draft",
    )
    db.add(session_row)
    db.commit()
    db.refresh(session_row)
    expected_age = format_dog_age(
        dog.birthday, session_calendar_date(session_row.created_at)
    )
    expected_days = days_since_status(dog.status_at, session_row.created_at)
    post(
        client,
        "/login",
        data={
            "email": settings.FIRST_SUPERUSER,
            "password": settings.FIRST_SUPERUSER_PASSWORD,
        },
    )
    page = client.get(f"/sessions/{session_row.id}")
    assert page.status_code == 200
    assert "сука" in page.text
    assert "female" not in page.text
    assert "метис" in page.text
    assert "дома" in page.text
    assert "home" not in page.text
    assert expected_age in page.text
    assert str(expected_days) in page.text
    assert "12.5" in page.text
    assert "из приюта" in page.text


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
            display_num=1,
        )
    )
    session_row = SurveySession(
        owner_id=_create_owner(db).id,
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
    post(
        client,
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


def test_users_page_shows_group(client: TestClient, db: Session) -> None:
    current = db.exec(
        select(User).where(User.email == settings.FIRST_SUPERUSER)
    ).first()
    assert current
    _login_superuser(client)
    page = client.get("/users")
    assert page.status_code == 200
    assert ">group<" in page.text
    assert "expert" in page.text
    assert "Создать администратора" in page.text
    assert f"/users/{current.id}" in page.text
    assert "/users/new" in page.text


def test_users_new_forbidden_for_non_superuser(client: TestClient, db: Session) -> None:
    password = f"Exp1-{random_lower_string()[:8]}"
    email = f"expert-{random_lower_string()}@example.com"
    crud.create_user(
        session=db,
        user_create=UserCreate(
            email=email,
            password=password,
            group=UserGroup.EXPERT,
        ),
    )
    post(client, "/login", data={"email": email, "password": password})
    page = client.get("/users/new", follow_redirects=False)
    assert page.status_code == 403
    create = post(
        client,
        "/users/new",
        data={
            "email": f"blocked-{random_lower_string()}@example.com",
            "password": "Secret12",
            "group": "expert",
            "is_active": "true",
            "is_superuser": "false",
        },
        follow_redirects=False,
    )
    assert create.status_code == 403


def test_admin_can_manage_regular_users_but_cannot_grant_superuser(
    client: TestClient, db: Session
) -> None:
    _login_admin(client, db)
    form = client.get("/users/new")
    assert form.status_code == 200
    assert 'name="is_superuser" value="false"' in form.text

    regular_email = f"regular-{random_lower_string()}@example.com"
    created = post(
        client,
        "/users/new",
        data={
            "email": regular_email,
            "password": "Secret12",
            "group": "expert",
            "is_active": "true",
            "is_superuser": "false",
        },
        follow_redirects=False,
    )
    assert created.status_code == 303
    regular = db.exec(select(User).where(User.email == regular_email)).first()
    assert regular is not None
    assert regular.is_superuser is False

    blocked = post(
        client,
        "/users/new",
        data={
            "email": f"blocked-super-{random_lower_string()}@example.com",
            "password": "Secret12",
            "group": "admin",
            "is_active": "true",
            "is_superuser": "true",
        },
    )
    assert blocked.status_code == 403
    assert "Только superuser" in blocked.text


def test_user_create_and_update(client: TestClient, db: Session) -> None:
    _login_superuser(client)
    form = client.get("/users/new")
    assert form.status_code == 200
    assert "Новый администратор" in form.text
    assert "Создать" in form.text
    email = f"new-admin-{random_lower_string()}@example.com"
    response = post(
        client,
        "/users/new",
        data={
            "email": email,
            "password": "Secret12",
            "full_name": "Новый",
            "group": "admin",
            "phone": "+7000",
            "contact": "telegram",
            "is_active": "true",
            "is_superuser": "false",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    created = db.exec(select(User).where(User.email == email)).first()
    assert created is not None
    assert created.group == UserGroup.ADMIN
    assert created.full_name == "Новый"
    assert created.phone == "+7000"
    assert created.is_superuser is False
    assert response.headers["location"] == f"/users/{created.id}"
    detail = client.get(f"/users/{created.id}")
    assert detail.status_code == 200
    assert created.email in detail.text
    assert "Сохранить" in detail.text
    update = post(
        client,
        f"/users/{created.id}",
        data={
            "email": email,
            "password": "",
            "full_name": "Обновлённый",
            "group": "expert",
            "phone": "+7111",
            "contact": "signal",
            "is_active": "true",
            "is_superuser": "false",
        },
        follow_redirects=False,
    )
    assert update.status_code == 303
    db.refresh(created)
    assert created.full_name == "Обновлённый"
    assert created.group == UserGroup.EXPERT
    assert created.phone == "+7111"


def test_user_create_rejects_duplicate_email(client: TestClient) -> None:
    _login_superuser(client)
    response = post(
        client,
        "/users/new",
        data={
            "email": settings.FIRST_SUPERUSER,
            "password": "Secret12",
            "full_name": "",
            "group": "expert",
            "phone": "",
            "contact": "",
            "is_active": "true",
            "is_superuser": "false",
        },
    )
    assert response.status_code == 400
    assert "уже занят" in response.text


def test_user_update_rejects_self_demote(client: TestClient, db: Session) -> None:
    current = db.exec(
        select(User).where(User.email == settings.FIRST_SUPERUSER)
    ).first()
    assert current
    _login_superuser(client)
    response = post(
        client,
        f"/users/{current.id}",
        data={
            "email": current.email,
            "password": "",
            "full_name": current.full_name or "",
            "group": current.group,
            "phone": current.phone or "",
            "contact": current.contact or "",
            "is_active": "true",
            "is_superuser": "false",
        },
    )
    assert response.status_code == 400
    assert "superuser" in response.text
    db.refresh(current)
    assert current.is_superuser is True


def _login_superuser(client: TestClient) -> None:
    post(
        client,
        "/login",
        data={
            "email": settings.FIRST_SUPERUSER,
            "password": settings.FIRST_SUPERUSER_PASSWORD,
        },
    )


def _create_owner(db: Session, name: str = "Владелец сессии") -> Owner:
    owner = Owner(name=name)
    db.add(owner)
    db.commit()
    db.refresh(owner)
    return owner


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
        owner_id=_create_owner(db, "Владелец рекомендаций").id,
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

    response = post(
        client,
        f"/sessions/{session_row.id}/recommendations",
        data={
            "recomendation_id": str(recommendation.id),
            "chart_number": "2",
            "weight": "0.75",
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
    assert saved.chart_number == 2
    assert saved.weight == 0.75

    detail = client.get(f"/sessions/{session_row.id}")
    assert detail.status_code == 200
    assert "Короткая прогулка" in detail.text
    assert "приоритет на первую неделю" in detail.text
    assert f"Автор рекомендации: {user.full_name or user.email}" in detail.text
    assert f'value="{recommendation.id}"' not in detail.text


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
    response = post(
        client,
        f"/sessions/{session_row.id}/recommendations",
        data={"recomendation_id": str(recommendation.id), "comment": ""},
    )
    assert response.status_code == 400
    assert "уже добавлена" in response.text


def test_user_can_delete_own_session_recommendation(
    client: TestClient, db: Session
) -> None:
    session_row, recommendation, user = _session_with_recommendation_catalog(db)
    row = SessionRecommendation(
        user_id=user.id,
        session_id=session_row.id,
        recomendation_id=recommendation.id,
        chart_number=0,
        weight=1.0,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    _login_superuser(client)
    row_id = row.id
    delete_path = f"/sessions/{session_row.id}/recommendations/{row_id}/delete"

    page = client.get(f"/sessions/{session_row.id}")
    assert delete_path in page.text
    response = post(client, delete_path, follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == f"/sessions/{session_row.id}"
    db.expire_all()
    assert db.get(SessionRecommendation, row_id) is None


def test_user_cannot_delete_another_users_session_recommendation(
    client: TestClient, db: Session
) -> None:
    session_row, recommendation, author = _session_with_recommendation_catalog(db)
    row = SessionRecommendation(
        user_id=author.id,
        session_id=session_row.id,
        recomendation_id=recommendation.id,
        chart_number=0,
        weight=1.0,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    _login_expert(client, db)
    delete_path = f"/sessions/{session_row.id}/recommendations/{row.id}/delete"

    page = client.get(f"/sessions/{session_row.id}")
    assert delete_path not in page.text
    assert f'name="recommendation_id" value="{row.id}"' not in page.text
    response = post(client, delete_path, follow_redirects=False)

    assert response.status_code == 403
    assert db.get(SessionRecommendation, row.id) is not None
    forged_update = post(
        client,
        f"/sessions/{session_row.id}/recommendations/save",
        data={
            "recommendation_id": [str(row.id)],
            "chart_number": ["2"],
            "weight": ["0.5"],
            "comment": ["чужое изменение"],
        },
        follow_redirects=False,
    )
    assert forged_update.status_code == 403


def test_session_recommendation_can_be_updated(client: TestClient, db: Session) -> None:
    session_row, recommendation, user = _session_with_recommendation_catalog(db)
    row = SessionRecommendation(
        user_id=user.id,
        session_id=session_row.id,
        recomendation_id=recommendation.id,
        chart_number=0,
        weight=1.0,
        comment="черновик",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    _login_superuser(client)
    page = client.get(f"/sessions/{session_row.id}")
    assert page.status_code == 200
    assert 'name="chart_number"' in page.text
    assert 'type="range"' in page.text
    assert "Критичность" in page.text
    assert page.text.count("Сохранить") == 1
    assert f"/sessions/{session_row.id}/recommendations/save" in page.text
    assert f'/sessions/{session_row.id}/recommendations/{row.id}"' not in page.text
    response = post(
        client,
        f"/sessions/{session_row.id}/recommendations/save",
        data={
            "recommendation_id": [str(row.id)],
            "chart_number": ["3"],
            "weight": ["0.4"],
            "comment": ["обновлено"],
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    db.refresh(row)
    assert row.chart_number == 3
    assert row.weight == 0.4
    assert row.comment == "обновлено"


def test_session_recommendations_can_be_saved_together(
    client: TestClient, db: Session
) -> None:
    session_row, first, user = _session_with_recommendation_catalog(db)
    second = Recommendation(
        name="Тишина",
        slug=f"quiet-{random_lower_string()}",
        text="Не шумите.",
    )
    db.add(second)
    db.commit()
    db.refresh(second)
    first_row = SessionRecommendation(
        user_id=user.id,
        session_id=session_row.id,
        recomendation_id=first.id,
        chart_number=0,
        weight=1.0,
        comment="черновик 1",
    )
    second_row = SessionRecommendation(
        user_id=user.id,
        session_id=session_row.id,
        recomendation_id=second.id,
        chart_number=1,
        weight=0.5,
        comment="черновик 2",
    )
    db.add(first_row)
    db.add(second_row)
    db.commit()
    db.refresh(first_row)
    db.refresh(second_row)
    _login_superuser(client)
    response = post(
        client,
        f"/sessions/{session_row.id}/recommendations/save",
        data={
            "recommendation_id": [str(first_row.id), str(second_row.id)],
            "chart_number": ["2", "4"],
            "weight": ["0.2", "0.8"],
            "comment": ["первая", "вторая"],
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    db.refresh(first_row)
    db.refresh(second_row)
    assert first_row.chart_number == 2
    assert first_row.weight == 0.2
    assert first_row.comment == "первая"
    assert second_row.chart_number == 4
    assert second_row.weight == 0.8
    assert second_row.comment == "вторая"


def test_session_recommendation_update_rejects_bad_weight(
    client: TestClient, db: Session
) -> None:
    session_row, recommendation, user = _session_with_recommendation_catalog(db)
    row = SessionRecommendation(
        user_id=user.id,
        session_id=session_row.id,
        recomendation_id=recommendation.id,
        chart_number=1,
        weight=0.5,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    _login_superuser(client)
    response = post(
        client,
        f"/sessions/{session_row.id}/recommendations/save",
        data={
            "recommendation_id": [str(row.id)],
            "chart_number": ["1"],
            "weight": ["2"],
            "comment": [""],
        },
    )
    assert response.status_code == 400
    assert "от 0 до 1" in response.text
    db.refresh(row)
    assert row.weight == 0.5


def _login_admin(client: TestClient, db: Session) -> User:
    password = f"Adm1n-{random_lower_string()[:8]}"
    user = crud.create_user(
        session=db,
        user_create=UserCreate(
            email=f"admin-{random_lower_string()}@example.com",
            password=password,
            group=UserGroup.ADMIN,
        ),
    )
    post(client, "/login", data={"email": user.email, "password": password})
    return user


def _login_expert(client: TestClient, db: Session) -> User:
    password = f"Exp1-{random_lower_string()[:8]}"
    user = crud.create_user(
        session=db,
        user_create=UserCreate(
            email=f"expert-{random_lower_string()}@example.com",
            password=password,
            group=UserGroup.EXPERT,
        ),
    )
    post(client, "/login", data={"email": user.email, "password": password})
    return user


def test_expert_access_matrix(client: TestClient, db: Session) -> None:
    _login_expert(client, db)
    for path in ("/surveys", "/scales", "/sessions"):
        assert client.get(path).status_code == 200
    for path in (
        "/dogs",
        "/recommendations",
        "/users",
        "/dictionaries",
        "/answer-events",
        "/owners",
    ):
        assert client.get(path, follow_redirects=False).status_code == 403

    home = client.get("/")
    assert 'href="/surveys"' in home.text
    assert 'href="/scales"' in home.text
    assert 'href="/sessions"' in home.text
    assert 'href="/dogs"' not in home.text
    assert 'href="/recommendations"' not in home.text
    assert 'href="/users"' not in home.text


def test_admin_access_matrix(client: TestClient, db: Session) -> None:
    _login_admin(client, db)
    for path in (
        "/dogs",
        "/surveys",
        "/scales",
        "/sessions",
        "/recommendations",
        "/users",
    ):
        assert client.get(path).status_code == 200
    for path in ("/dictionaries", "/answer-events", "/owners"):
        assert client.get(path, follow_redirects=False).status_code == 403

    home = client.get("/")
    for path in (
        "/dogs",
        "/surveys",
        "/scales",
        "/sessions",
        "/recommendations",
        "/users",
    ):
        assert f'href="{path}"' in home.text
    assert 'href="/dictionaries"' not in home.text
    assert 'href="/answer-events"' not in home.text
    assert 'href="/owners"' not in home.text


def test_admin_can_create_and_edit_recommendation(
    client: TestClient, db: Session
) -> None:
    _login_admin(client, db)
    listing = client.get("/recommendations")
    assert listing.status_code == 200
    assert 'href="/recommendations/new"' in listing.text
    form = client.get("/recommendations/new")
    assert form.status_code == 200
    assert "Новая рекомендация" in form.text
    slug = f"rec-{random_lower_string()}"
    created = post(
        client,
        "/recommendations/new",
        data={
            "name": "Прогулка",
            "slug": slug,
            "text": "Выходите дважды в день",
            "description": "Коротко",
            "group": "other",
        },
        follow_redirects=False,
    )
    assert created.status_code == 303
    row = db.exec(select(Recommendation).where(Recommendation.slug == slug)).one()
    assert created.headers["location"] == f"/recommendations/{row.id}"
    assert row.name == "Прогулка"
    assert row.text == "Выходите дважды в день"
    assert row.description == "Коротко"
    page = client.get(f"/recommendations/{row.id}")
    assert page.status_code == 200
    assert "Сохранить" in page.text
    updated = post(
        client,
        f"/recommendations/{row.id}",
        data={
            "name": "Длинная прогулка",
            "slug": slug,
            "text": "Выходите трижды в день",
            "description": "",
            "group": "other",
        },
        follow_redirects=False,
    )
    assert updated.status_code == 303
    db.refresh(row)
    assert row.name == "Длинная прогулка"
    assert row.description is None
    duplicate = post(
        client,
        "/recommendations/new",
        data={
            "name": "Другая",
            "slug": slug,
            "text": "Текст",
            "description": "",
            "group": "other",
        },
    )
    assert duplicate.status_code == 400
    assert "slug" in duplicate.text
    missing = post(
        client,
        "/recommendations/new",
        data={
            "name": "",
            "slug": f"empty-{random_lower_string()}",
            "text": "Текст",
            "description": "",
            "group": "other",
        },
    )
    assert missing.status_code == 400
    assert "обязательны" in missing.text


def test_expert_cannot_open_recommendation_form(
    client: TestClient, db: Session
) -> None:
    row = Recommendation(
        name="Closed",
        slug=f"closed-{random_lower_string()}",
        text="Text",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    _login_expert(client, db)
    assert client.get("/recommendations/new", follow_redirects=False).status_code == 403
    assert (
        client.get(f"/recommendations/{row.id}", follow_redirects=False).status_code
        == 403
    )
    response = post(
        client,
        f"/recommendations/{row.id}",
        data={
            "name": "Changed",
            "slug": row.slug,
            "text": "Changed",
            "description": "",
            "group": "other",
        },
    )
    assert response.status_code == 403


def test_scales_page_visible_to_logged_in_user(client: TestClient, db: Session) -> None:
    scale = Scale(
        name="Частота лая",
        type="integer",
        config={"min_value": 0, "max_value": 4},
    )
    db.add(scale)
    db.commit()
    db.refresh(scale)
    _login_superuser(client)
    page = client.get("/scales")
    assert page.status_code == 200
    assert "Шкалы" in page.text
    assert "Частота лая" in page.text
    detail = client.get(f"/scales/{scale.id}")
    assert detail.status_code == 200
    assert "Сохранить" in detail.text


def test_scale_update_forbidden_for_expert(client: TestClient, db: Session) -> None:
    scale = Scale(
        name="Expert scale",
        type="integer",
        config={"min_value": 0, "max_value": 4},
    )
    db.add(scale)
    db.commit()
    db.refresh(scale)
    _login_expert(client, db)
    response = post(
        client,
        f"/scales/{scale.id}",
        data={
            "name": "Changed",
            "type": "integer",
            "description": "",
            "config": "",
        },
    )
    assert response.status_code == 403


def test_scale_update_allowed_for_admin(client: TestClient, db: Session) -> None:
    scale = Scale(
        name="Admin scale",
        type="integer",
        config={"min_value": 0, "max_value": 4},
    )
    db.add(scale)
    db.commit()
    db.refresh(scale)
    _login_admin(client, db)
    page = client.get(f"/scales/{scale.id}")
    assert page.status_code == 200
    assert "Сохранить" in page.text
    response = post(
        client,
        f"/scales/{scale.id}",
        data={
            "name": "Updated scale",
            "type": "integer",
            "description": "после правки",
            "config": '{"min_value": 0, "max_value": 5}',
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    db.refresh(scale)
    assert scale.name == "Updated scale"
    assert scale.description == "после правки"
    assert scale.config == {"min_value": 0, "max_value": 5}


def test_dictionaries_page_lists_and_opens_row(client: TestClient, db: Session) -> None:
    user = db.exec(select(User).where(User.email == settings.FIRST_SUPERUSER)).first()
    assert user
    key = f"ns::{random_lower_string()}"
    db.add(
        Dictionary(
            key=key,
            value={"female": "сука"},
            created_by=user.id,
            updated_by=user.id,
        )
    )
    db.commit()
    _login_superuser(client)
    page = client.get("/dictionaries")
    assert page.status_code == 200
    assert "Справочники" in page.text
    assert key in page.text
    assert f"/dictionaries/{key}" in page.text
    detail = client.get(f"/dictionaries/{key}")
    assert detail.status_code == 200
    assert key in detail.text
    assert "сука" in detail.text
    assert "Сохранить" in detail.text


def test_dictionary_can_be_updated(client: TestClient, db: Session) -> None:
    user = db.exec(select(User).where(User.email == settings.FIRST_SUPERUSER)).first()
    assert user
    key = f"ref-{random_lower_string()}"
    row = Dictionary(
        key=key,
        value={"home": "дом"},
        created_by=user.id,
        updated_by=user.id,
    )
    db.add(row)
    db.commit()
    _login_superuser(client)
    response = post(
        client,
        f"/dictionaries/{key}",
        data={"value": '{"home": "дома", "shelter": "приют"}'},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == f"/dictionaries/{key}"
    db.refresh(row)
    assert row.value == {"home": "дома", "shelter": "приют"}
    assert row.updated_by == user.id


def test_dictionary_update_rejects_invalid_json(
    client: TestClient, db: Session
) -> None:
    user = db.exec(select(User).where(User.email == settings.FIRST_SUPERUSER)).first()
    assert user
    key = f"ref-{random_lower_string()}"
    row = Dictionary(
        key=key,
        value={"ok": True},
        created_by=user.id,
        updated_by=user.id,
    )
    db.add(row)
    db.commit()
    _login_superuser(client)
    response = post(
        client,
        f"/dictionaries/{key}",
        data={"value": "{not json"},
    )
    assert response.status_code == 400
    assert "Некорректный JSON" in response.text
    db.refresh(row)
    assert row.value == {"ok": True}


def test_survey_detail_sorts_questions_by_display_num(
    client: TestClient, db: Session
) -> None:
    survey = Survey(name="Display order", slug=f"display-order-{random_lower_string()}")
    scale = Scale(name="Балл", type="integer", config={"min_value": 0, "max_value": 4})
    db.add(survey)
    db.add(scale)
    db.commit()
    db.refresh(survey)
    db.refresh(scale)
    version = SurveyVersion(survey_id=survey.id, version_num=1)
    later = Question(text="Показывается вторым", scale_id=scale.id)
    earlier = Question(text="Показывается первым", scale_id=scale.id)
    db.add(version)
    db.add(later)
    db.add(earlier)
    db.commit()
    db.refresh(version)
    db.refresh(later)
    db.refresh(earlier)
    db.add(
        SurveyQuestion(
            survey_version_id=version.id,
            question_id=later.id,
            order_num=1,
            display_num=2,
        )
    )
    db.add(
        SurveyQuestion(
            survey_version_id=version.id,
            question_id=earlier.id,
            order_num=2,
            display_num=1,
        )
    )
    db.commit()
    _login_superuser(client)
    page = client.get(f"/surveys/{survey.id}")
    assert page.status_code == 200
    assert page.text.index("Показывается первым") < page.text.index(
        "Показывается вторым"
    )
    assert "display_num ↑" in page.text
    by_order = client.get(f"/surveys/{survey.id}?sort=order")
    assert by_order.status_code == 200
    assert "order ↑" in by_order.text
    assert by_order.text.index("Показывается вторым") < by_order.text.index(
        "Показывается первым"
    )
    by_order_desc = client.get(f"/surveys/{survey.id}?sort=-order")
    assert "order ↓" in by_order_desc.text
    assert by_order_desc.text.index("Показывается первым") < by_order_desc.text.index(
        "Показывается вторым"
    )
    by_display_desc = client.get(f"/surveys/{survey.id}?sort=-display")
    assert "display_num ↓" in by_display_desc.text
    assert by_display_desc.text.index(
        "Показывается вторым"
    ) < by_display_desc.text.index("Показывается первым")
    saved = client.post(
        f"/surveys/{survey.id}",
        data={
            "csrf_token": client.cookies[CSRF_COOKIE_NAME],
            "question_id": [str(later.id), str(earlier.id)],
            "display_num": ["2", "1"],
            "group": ["other", "other"],
            "sort": "order",
        },
        follow_redirects=False,
    )
    assert saved.status_code == 303
    assert saved.headers["location"].endswith("?sort=order")


def test_admin_can_edit_survey_question_layout(client: TestClient, db: Session) -> None:
    survey = Survey(name="Editable survey", slug=f"editable-{random_lower_string()}")
    scale = Scale(name="Балл", type="integer", config={"min_value": 0, "max_value": 4})
    db.add(survey)
    db.add(scale)
    db.commit()
    db.refresh(survey)
    db.refresh(scale)
    version = SurveyVersion(survey_id=survey.id, version_num=1)
    question = Question(text="Можно переставить", scale_id=scale.id)
    db.add(version)
    db.add(question)
    db.commit()
    db.refresh(version)
    db.refresh(question)
    link = SurveyQuestion(
        survey_version_id=version.id,
        question_id=question.id,
        order_num=1,
        display_num=3,
        group="other",
    )
    db.add(link)
    db.commit()
    _login_admin(client, db)
    page = client.get(f"/surveys/{survey.id}")
    assert page.status_code == 200
    assert 'name="display_num"' in page.text
    assert 'name="group"' in page.text
    assert "Сохранить" in page.text
    saved = post(
        client,
        f"/surveys/{survey.id}",
        data={
            "question_id": str(question.id),
            "display_num": "1",
            "group": "Household",
        },
        follow_redirects=False,
    )
    assert saved.status_code == 303
    db.refresh(link)
    assert link.display_num == 1
    assert link.group == "Household"
    cleared = post(
        client,
        f"/surveys/{survey.id}",
        data={
            "question_id": str(question.id),
            "display_num": "",
            "group": "Household",
        },
        follow_redirects=False,
    )
    assert cleared.status_code == 400
    assert "обязателен" in cleared.text
    db.refresh(link)
    assert link.display_num == 1
    invalid = post(
        client,
        f"/surveys/{survey.id}",
        data={
            "question_id": str(question.id),
            "display_num": "нет",
            "group": "Household",
        },
    )
    assert invalid.status_code == 400
    assert "целым" in invalid.text
    db.refresh(link)
    assert link.display_num == 1


def test_expert_cannot_edit_survey_question_layout(
    client: TestClient, db: Session
) -> None:
    survey = Survey(name="Read only survey", slug=f"readonly-{random_lower_string()}")
    scale = Scale(name="Балл", type="integer", config={"min_value": 0, "max_value": 4})
    db.add(survey)
    db.add(scale)
    db.commit()
    db.refresh(survey)
    db.refresh(scale)
    version = SurveyVersion(survey_id=survey.id, version_num=1)
    question = Question(text="Только чтение", scale_id=scale.id)
    db.add(version)
    db.add(question)
    db.commit()
    db.refresh(version)
    db.refresh(question)
    link = SurveyQuestion(
        survey_version_id=version.id,
        question_id=question.id,
        order_num=1,
        display_num=1,
        group="other",
    )
    db.add(link)
    db.commit()
    _login_expert(client, db)
    page = client.get(f"/surveys/{survey.id}")
    assert page.status_code == 200
    assert "Сохранить" not in page.text
    assert 'name="group"' not in page.text
    response = post(
        client,
        f"/surveys/{survey.id}",
        data={
            "question_id": str(question.id),
            "display_num": "2",
            "group": "Household",
        },
    )
    assert response.status_code == 403
    db.refresh(link)
    assert link.group == "other"
    assert link.display_num == 1


def test_json_api_is_gone(client: TestClient) -> None:
    response = client.get("/api/v1/surveys/")
    assert response.status_code == 404


def test_session_detail_groups_answers_by_cbarq_domains(
    client: TestClient, db: Session
) -> None:
    user = db.exec(select(User).where(User.email == settings.FIRST_SUPERUSER)).first()
    assert user
    dog = Dog(name="Domain Dog")
    survey = Survey(name="Domain Survey", slug=f"domains-{random_lower_string()}")
    scale = Scale(
        name="Балл доменов",
        type="integer",
        config={"min_value": 0, "max_value": 4},
    )
    db.add(dog)
    db.add(survey)
    db.add(scale)
    group_labels = {
        "Excitability": {"name": "Возбудимость", "color": "var(--bs-orange)"},
        "Trainability": {
            "name": "Трудность дрессировки",
            "color": "var(--bs-green)",
        },
    }
    group_row = db.get(Dictionary, SURVEYS_QUESTIONS_GROUP_KEY)
    if group_row is None:
        db.add(
            Dictionary(
                key=SURVEYS_QUESTIONS_GROUP_KEY,
                value=group_labels,
                created_by=user.id,
                updated_by=user.id,
            )
        )
    else:
        group_row.value = group_labels
        db.add(group_row)
    consts_value = {"c-barq-short-42": {"domain_threshold": 0.5, "reverse": [27, 28]}}
    consts_row = db.get(Dictionary, SURVEYS_QUESTIONS_CONSTS_KEY)
    if consts_row is None:
        db.add(
            Dictionary(
                key=SURVEYS_QUESTIONS_CONSTS_KEY,
                value=consts_value,
                created_by=user.id,
                updated_by=user.id,
            )
        )
    else:
        consts_row.value = consts_value
        db.add(consts_row)
    db.commit()
    db.refresh(dog)
    db.refresh(survey)
    db.refresh(scale)
    version = SurveyVersion(survey_id=survey.id, version_num=1)
    db.add(version)
    db.commit()
    db.refresh(version)
    texts = {
        1: ("Возбуждается дома", "Excitability"),
        2: ("Возбуждается на улице", "Excitability"),
        11: ("Знакомая собака", "Dog_rivalry"),
        27: ("Сразу сидит", "Trainability"),
        28: ("Сразу жди", "Trainability"),
        29: ("Легко отвлекается", "Trainability"),
        32: ("Тянет поводок", "other"),
        99: ("Общий вопрос", "other"),
    }
    questions: dict[int, Question] = {}
    for order, (text, group) in texts.items():
        question = Question(text=text, scale_id=scale.id)
        db.add(question)
        db.commit()
        db.refresh(question)
        questions[order] = question
        db.add(
            SurveyQuestion(
                survey_version_id=version.id,
                question_id=question.id,
                order_num=order,
                display_num=order,
                group=group,
            )
        )
    session_row = SurveySession(
        owner_id=_create_owner(db).id,
        dog_id=dog.id,
        survey_version_id=version.id,
        status="draft",
    )
    db.add(session_row)
    db.commit()
    db.refresh(session_row)
    values = {1: 2, 2: 4, 27: 0, 32: 3, 99: 1}
    for order, value in values.items():
        db.add(
            AnswerEvent(
                surveys_session_id=session_row.id,
                survey_version_id=version.id,
                question_id=questions[order].id,
                value={"value": value},
            )
        )
    db.commit()
    _login_superuser(client)
    page = client.get(f"/sessions/{session_row.id}")
    assert page.status_code == 200
    assert "По доменам" in page.text
    assert "Возбудимость" in page.text
    assert "7.50" in page.text
    assert "из 10" in page.text
    assert "2 из 2" in page.text
    assert "Трудность дрессировки" not in page.text
    assert "мало ответов" not in page.text
    assert "Dog_rivalry" not in page.text
    assert "Прочее" not in page.text
    assert "Вне скоринга" in page.text
    assert "Общий вопрос" in page.text
    assert 'id="category"' not in page.text
    flat = client.get(f"/sessions/{session_row.id}", params={"view": "flat"})
    assert flat.status_code == 200
    assert "Все категории" in flat.text
    assert "Возбуждается дома" in flat.text
    assert "Общий вопрос" in flat.text
    filtered = client.get(
        f"/sessions/{session_row.id}",
        params={"view": "flat", "answer": "4"},
    )
    assert "Возбуждается на улице" in filtered.text
    assert "Общий вопрос" not in filtered.text


def test_sessions_page_shows_answer_percent(client: TestClient, db: Session) -> None:
    owner = _create_owner(db, "Владелец процента списка")
    dog = Dog(name="Listed Percent Dog")
    empty_dog = Dog(name="Listed Empty Dog")
    survey = Survey(name="Listed Percent", slug=f"listed-{random_lower_string()}")
    scale = Scale(
        name="Балл списка", type="integer", config={"min_value": 0, "max_value": 4}
    )
    db.add(dog)
    db.add(empty_dog)
    db.add(survey)
    db.add(scale)
    db.commit()
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
    first = Question(text="Список 1", scale_id=scale.id)
    second = Question(text="Список 2", scale_id=scale.id)
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
            value={"value": 1},
            created_at=datetime(2026, 2, 1, tzinfo=UTC),
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
    _login_superuser(client)
    page = client.get("/sessions")
    assert page.status_code == 200
    assert "Ответов, %" in page.text
    assert re.search(r"Listed Percent · v1\s*</td>\s*<td>\s*50\s*</td>", page.text)
    assert re.search(r"Listed Percent · v2\s*</td>\s*<td>\s*—\s*</td>", page.text)


def test_health_check(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_post_without_csrf_token_is_rejected(client: TestClient) -> None:
    client.get("/login")
    response = client.post(
        "/login",
        data={
            "email": settings.FIRST_SUPERUSER,
            "password": settings.FIRST_SUPERUSER_PASSWORD,
        },
        follow_redirects=False,
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "CSRF check failed"


def test_post_with_foreign_csrf_token_is_rejected(client: TestClient) -> None:
    client.get("/login")
    response = client.post(
        "/login",
        data={
            "email": settings.FIRST_SUPERUSER,
            "password": settings.FIRST_SUPERUSER_PASSWORD,
            "csrf_token": "not-the-cookie",
        },
        follow_redirects=False,
    )
    assert response.status_code == 403


def test_logout_is_post_only(client: TestClient) -> None:
    missing = client.get("/logout", follow_redirects=False)
    assert missing.status_code == 405
    response = post(client, "/logout", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"
    post(
        client,
        "/login",
        data={
            "email": settings.FIRST_SUPERUSER,
            "password": settings.FIRST_SUPERUSER_PASSWORD,
        },
        follow_redirects=False,
    )
