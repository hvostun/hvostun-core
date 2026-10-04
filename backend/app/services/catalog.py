import uuid
from collections.abc import Sequence

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, func, select

from app.models import (
    Question,
    Recommendation,
    RecommendationGroup,
    Scale,
    ScaleType,
    Survey,
    SurveyQuestion,
    SurveyVersion,
)


class CatalogNotFoundError(LookupError):
    pass


class CatalogUpdateError(ValueError):
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
        .order_by(
            col(SurveyQuestion.display_num),
            col(SurveyQuestion.order_num),
            col(Question.id),
        )
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


def update_survey_question_layout(
    session: Session,
    survey_version_id: uuid.UUID,
    updates: Sequence[tuple[uuid.UUID, int | None, str]],
) -> None:
    links = {
        link.question_id: link
        for _question, _scale, link in get_version_questions(session, survey_version_id)
    }
    question_ids = [question_id for question_id, _display_num, _group in updates]
    if set(question_ids) != set(links) or len(question_ids) != len(links):
        raise CatalogUpdateError("Некорректные данные вопросов")
    for question_id, display_num, group in updates:
        link = links[question_id]
        link.display_num = display_num
        link.group = group.strip()
    session.commit()


def get_recommendation(session: Session, recommendation_id: uuid.UUID) -> Recommendation:
    row = session.get(Recommendation, recommendation_id)
    if row is None:
        raise CatalogNotFoundError("Recommendation not found")
    return row


def create_recommendation(
    session: Session,
    *,
    name: str,
    slug: str,
    text: str,
    description: str | None,
    group: RecommendationGroup,
) -> Recommendation:
    row = Recommendation(
        name=name,
        slug=slug,
        text=text,
        description=description,
        group=group,
    )
    session.add(row)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise CatalogUpdateError("Такой slug уже есть") from exc
    session.refresh(row)
    return row


def update_recommendation(
    session: Session,
    recommendation_id: uuid.UUID,
    *,
    name: str,
    slug: str,
    text: str,
    description: str | None,
    group: RecommendationGroup,
) -> Recommendation:
    row = get_recommendation(session, recommendation_id)
    row.name = name
    row.slug = slug
    row.text = text
    row.description = description
    row.group = group
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise CatalogUpdateError("Такой slug уже есть") from exc
    session.refresh(row)
    return row
