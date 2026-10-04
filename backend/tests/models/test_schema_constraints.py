from sqlalchemy import inspect
from sqlmodel import Session


def test_all_foreign_keys_use_restrict(db: Session) -> None:
    inspector = inspect(db.get_bind())
    tables = set(inspector.get_table_names()) - {"alembic_version"}
    foreign_keys = [
        foreign_key
        for table in tables
        for foreign_key in inspector.get_foreign_keys(table)
    ]
    assert foreign_keys
    assert all(
        foreign_key["options"].get("ondelete") == "RESTRICT"
        for foreign_key in foreign_keys
    )


def test_dogs_have_measurement_columns(db: Session) -> None:
    inspector = inspect(db.get_bind())
    columns = {column["name"]: column for column in inspector.get_columns("dogs")}
    assert columns["firstdog"]["nullable"] is False
    assert columns["weight"]["nullable"] is True
    assert columns["height"]["nullable"] is True
    assert columns["history"]["nullable"] is True


def test_users_group_check_constraint_exists(db: Session) -> None:
    inspector = inspect(db.get_bind())
    names = {
        constraint["name"] for constraint in inspector.get_check_constraints("users")
    }
    assert "ck_users_group" in names


def test_survey_session_owner_references_owners(db: Session) -> None:
    inspector = inspect(db.get_bind())
    owner_fk = next(
        foreign_key
        for foreign_key in inspector.get_foreign_keys("survey_sessions")
        if foreign_key["constrained_columns"] == ["owner_id"]
    )
    assert owner_fk["name"] == "fk_survey_sessions_owner_id"
    assert owner_fk["referred_table"] == "owners"
    assert owner_fk["referred_columns"] == ["id"]


def test_catalog_group_check_constraints_exist(db: Session) -> None:
    inspector = inspect(db.get_bind())
    surveys_questions = {
        constraint["name"]
        for constraint in inspector.get_check_constraints("surveys_questions")
    }
    recommendations = {
        constraint["name"]
        for constraint in inspector.get_check_constraints("recommendations")
    }
    assert "ck_surveys_questions_group" not in surveys_questions
    assert "ck_recommendations_group" in recommendations
    question_columns = {
        column["name"] for column in inspector.get_columns("surveys_questions")
    }
    recommendation_columns = {
        column["name"] for column in inspector.get_columns("recommendations")
    }
    assert "group" in question_columns
    assert "group" in recommendation_columns


def test_questions_have_no_type_column(db: Session) -> None:
    inspector = inspect(db.get_bind())
    columns = {column["name"] for column in inspector.get_columns("questions")}
    assert "type" not in columns
    assert "global_id" not in columns
    names = {
        constraint["name"]
        for constraint in inspector.get_check_constraints("questions")
    }
    assert "ck_questions_type" not in names


def test_version_indexes_exist_without_duplicates(db: Session) -> None:
    inspector = inspect(db.get_bind())
    expected = {
        "survey_sessions": {
            "ix_survey_sessions_version_created",
            "ix_survey_sessions_owner_created",
            "ix_survey_sessions_dog_created",
            "ix_survey_sessions_status_created",
        },
        "answer_events": {
            "ix_answer_events_session_question_created",
            "ix_answer_events_session_version",
            "ix_answer_events_version_question",
            "ix_answer_events_question_id",
        },
        "surveys_questions": {
            "ix_surveys_questions_question_id",
            "ix_surveys_questions_user_id",
        },
    }
    for table, names in expected.items():
        actual = {index["name"] for index in inspector.get_indexes(table)}
        assert names <= actual
        assert len(actual) == len(set(actual))
