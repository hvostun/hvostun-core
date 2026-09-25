from sqlalchemy import inspect
from sqlmodel import Session

from app.models import Question, QuestionType, Scale


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


def test_users_group_check_constraint_exists(db: Session) -> None:
    inspector = inspect(db.get_bind())
    names = {
        constraint["name"] for constraint in inspector.get_check_constraints("users")
    }
    assert "ck_users_group" in names


def test_questions_type_check_constraint_exists(db: Session) -> None:
    inspector = inspect(db.get_bind())
    names = {
        constraint["name"]
        for constraint in inspector.get_check_constraints("questions")
    }
    assert "ck_questions_type" in names
    columns = {column["name"] for column in inspector.get_columns("questions")}
    assert "type" in columns
    assert "global_id" not in columns


def test_question_type_defaults_to_unknown(db: Session) -> None:
    scale = Scale(
        name="Default type scale",
        type="integer",
        config={"min_value": 0, "max_value": 1},
    )
    db.add(scale)
    db.commit()
    question = Question(text="Default type question", scale_id=scale.id)
    db.add(question)
    db.commit()
    db.refresh(question)
    assert question.type == QuestionType.UNKNOWN


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
