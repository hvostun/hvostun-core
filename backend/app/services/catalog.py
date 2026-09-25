import uuid
from collections.abc import Sequence

from sqlmodel import Session, col, func, select

from app.models import (
    Question,
    Scale,
    ScaleType,
    Survey,
    SurveyQuestion,
    SurveyVersion,
)


class CatalogNotFoundError(LookupError):
    pass


def get_scale(session: Session, scale_id: uuid.UUID) -> Scale:
    scale = session.get(Scale, scale_id)
    if scale is None:
        raise CatalogNotFoundError("Scale not found")
    return scale


def update_scale(
    session: Session,
    scale_id: uuid.UUID,
    *,
    name: str,
    description: str | None,
    type: ScaleType,
    config: dict[str, object] | None,
) -> Scale:
    scale = get_scale(session, scale_id)
    scale.name = name
    scale.description = description or None
    scale.type = type
    scale.config = config
    session.add(scale)
    session.commit()
    session.refresh(scale)
    return scale


def get_survey(session: Session, survey_id: uuid.UUID) -> Survey:
    survey = session.get(Survey, survey_id)
    if survey is None:
        raise CatalogNotFoundError("Survey not found")
    return survey


def get_survey_version(session: Session, survey_version_id: uuid.UUID) -> SurveyVersion:
    version = session.get(SurveyVersion, survey_version_id)
    if version is None:
        raise CatalogNotFoundError("Survey version not found")
    return version


def get_latest_survey_version(session: Session, survey_id: uuid.UUID) -> SurveyVersion:
    get_survey(session, survey_id)
    version = session.exec(
        select(SurveyVersion)
        .where(SurveyVersion.survey_id == survey_id)
        .order_by(col(SurveyVersion.version_num).desc())
        .limit(1)
    ).first()
    if version is None:
        raise CatalogNotFoundError("Survey has no versions")
    return version


def list_survey_versions(session: Session, survey_id: uuid.UUID) -> list[SurveyVersion]:
    get_survey(session, survey_id)
    return list(
        session.exec(
            select(SurveyVersion)
            .where(SurveyVersion.survey_id == survey_id)
            .order_by(col(SurveyVersion.version_num).desc())
        ).all()
    )


def get_version_questions(
    session: Session, survey_version_id: uuid.UUID
) -> list[tuple[Question, Scale, SurveyQuestion]]:
    get_survey_version(session, survey_version_id)
    rows = session.exec(
        select(Question, Scale, SurveyQuestion)
        .where(SurveyQuestion.survey_version_id == survey_version_id)
        .where(SurveyQuestion.question_id == Question.id)
        .where(Question.scale_id == Scale.id)
        .order_by(col(SurveyQuestion.order_num), col(Question.id))
    ).all()
    return list(rows)


def create_survey_version(
    session: Session,
    *,
    survey_id: uuid.UUID,
    description: str | None,
    questions: Sequence[tuple[uuid.UUID, int]],
    user_id: uuid.UUID | None = None,
) -> SurveyVersion:
    survey = session.exec(
        select(Survey).where(Survey.id == survey_id).with_for_update()
    ).first()
    if survey is None:
        raise CatalogNotFoundError("Survey not found")
    latest = session.exec(
        select(func.max(SurveyVersion.version_num)).where(
            SurveyVersion.survey_id == survey_id
        )
    ).one()
    version = SurveyVersion(
        survey_id=survey_id,
        version_num=(latest or 0) + 1,
        description=description,
    )
    session.add(version)
    session.flush()
    for question_id, order_num in questions:
        session.add(
            SurveyQuestion(
                survey_version_id=version.id,
                question_id=question_id,
                order_num=order_num,
                user_id=user_id,
            )
        )
    session.commit()
    session.refresh(version)
    return version
