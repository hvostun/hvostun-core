import re
import uuid
from datetime import date

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app import crud
from app.admin.deps import COOKIE_NAME
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
from app.services.sessions import (
    days_since_status,
    format_dog_age,
    session_calendar_date,
)
from tests.utils.utils import random_lower_string


def test_login_page_is_html(client: TestClient) -> None:
    response = client.get("/login")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Войти" in response.text
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
    response = client.post(
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
    response = client.post(
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
        r"C-BARQ Sessions · v1\s*</td>\s*<td>\s*0\s*</td>\s*<td>\s*0\s*</td>",
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
    survey = Survey(name="C-BARQ Rec Counts", slug=f"cbarq-rec-counts-{random_lower_string()}")
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
    client.post(
        "/login",
        data={
            "email": settings.FIRST_SUPERUSER,
            "password": settings.FIRST_SUPERUSER_PASSWORD,
        },
    )
    sessions = client.get("/sessions")
    assert sessions.status_code == 200
    assert "Rex Rec Counts" in sessions.text
    assert re.search(
        r"C-BARQ Rec Counts · v1\s*</td>\s*<td>\s*3\s*</td>\s*<td>\s*2\s*</td>",
        sessions.text,
    )
    assert 'name="has_my_recommendation"' not in sessions.text
    mine_row = re.search(r"Rex Rec Counts.*?</tr>", sessions.text, re.S)
    empty_row = re.search(r"Rex Without Recommendations.*?</tr>", sessions.text, re.S)
    assert mine_row is not None and "checked" in mine_row.group(0)
    assert empty_row is not None and "checked" not in empty_row.group(0)

    ascending = client.get("/sessions", params={"users_sort": "asc"})
    assert ascending.text.index("Rex Without Recommendations") < ascending.text.index(
        "Rex Rec Counts"
    )
    descending = client.get("/sessions", params={"users_sort": "desc"})
    assert descending.text.index("Rex Rec Counts") < descending.text.index(
        "Rex Without Recommendations"
    )


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
    db.add(
        Dictionary(
            key="surveys_questions::group",
            value={"other": "Прочее", "Excitability": "Возбудимость"},
            created_by=user.id,
            updated_by=user.id,
        )
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
    assert "Категория" in page.text
    assert "Прочее" in page.text
    assert 'value="other"' in page.text
    assert "Обычно" in page.text
    assert "progress-bar" in page.text
    assert "width: 75%" in page.text
    assert "var(--bs-blue)" in page.text
    assert "Значение" in page.text
    assert "№" in page.text
    assert "<td>1</td>" in page.text
    assert "Все категории" in page.text
    assert "Все ответы" in page.text


def test_session_detail_hides_progress_for_missing_answer(
    client: TestClient, db: Session
) -> None:
    user = db.exec(select(User).where(User.email == settings.FIRST_SUPERUSER)).first()
    assert user
    dog = Dog(name="Missing Bar Dog")
    survey = Survey(name="Missing Bar Survey", slug=f"missing-bar-{random_lower_string()}")
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
    page = client.get(f"/sessions/{session_row.id}")
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
            group="Excitability",
        )
    )
    db.add(
        SurveyQuestion(
            survey_version_id=version.id,
            question_id=second.id,
            order_num=2,
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
    page = client.get(f"/sessions/{session_row.id}")
    assert page.status_code == 200
    assert "Лает на гостей?" in page.text
    assert "Рычит на собак?" in page.text
    by_category = client.get(
        f"/sessions/{session_row.id}", params={"category": "Excitability"}
    )
    assert by_category.status_code == 200
    assert "Лает на гостей?" in by_category.text
    assert "Рычит на собак?" not in by_category.text
    by_answer = client.get(f"/sessions/{session_row.id}", params={"answer": "3"})
    assert "Лает на гостей?" in by_answer.text
    assert "Рычит на собак?" not in by_answer.text
    unanswered = client.get(
        f"/sessions/{session_row.id}", params={"answer": "unanswered"}
    )
    assert "Рычит на собак?" in unanswered.text
    assert "Лает на гостей?" not in unanswered.text
    empty = client.get(
        f"/sessions/{session_row.id}",
        params={"category": "Aggression", "answer": "3"},
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
    client.post(
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


def test_users_page_shows_group(client: TestClient, db: Session) -> None:
    current = db.exec(select(User).where(User.email == settings.FIRST_SUPERUSER)).first()
    assert current
    _login_superuser(client)
    page = client.get("/users")
    assert page.status_code == 200
    assert ">group<" in page.text
    assert "expert" in page.text
    assert "Создать администратора" in page.text
    assert f"/users/{current.id}" in page.text
    assert "/users/new" in page.text


def test_users_new_forbidden_for_non_superuser(
    client: TestClient, db: Session
) -> None:
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
    client.post("/login", data={"email": email, "password": password})
    page = client.get("/users/new", follow_redirects=False)
    assert page.status_code == 403
    create = client.post(
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
    created = client.post(
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

    blocked = client.post(
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
    response = client.post(
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
    update = client.post(
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
    response = client.post(
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
    current = db.exec(select(User).where(User.email == settings.FIRST_SUPERUSER)).first()
    assert current
    _login_superuser(client)
    response = client.post(
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
    client.post(
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

    response = client.post(
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
    response = client.post(
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
    response = client.post(delete_path, follow_redirects=False)

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
    response = client.post(delete_path, follow_redirects=False)

    assert response.status_code == 403
    assert db.get(SessionRecommendation, row.id) is not None
    forged_update = client.post(
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


def test_session_recommendation_can_be_updated(
    client: TestClient, db: Session
) -> None:
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
    response = client.post(
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
    response = client.post(
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
    response = client.post(
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
    client.post("/login", data={"email": user.email, "password": password})
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
    client.post("/login", data={"email": user.email, "password": password})
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
    response = client.post(
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
    response = client.post(
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


def test_dictionaries_page_lists_and_opens_row(
    client: TestClient, db: Session
) -> None:
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
    response = client.post(
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
    response = client.post(
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
    assert page.text.index("Показывается первым") < page.text.index("Показывается вторым")


def test_json_api_is_gone(client: TestClient) -> None:
    response = client.get("/api/v1/surveys/")
    assert response.status_code == 404


def test_health_check(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
