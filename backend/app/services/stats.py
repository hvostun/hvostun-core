import uuid
from dataclasses import dataclass

from sqlalchemy import tuple_
from sqlmodel import Session, col, func, select

from app.models import SessionRecommendation, User, UserGroup


@dataclass(frozen=True)
class ExpertTotals:
    surveys: int
    evaluations: int
    recommendations: int


@dataclass(frozen=True)
class ExpertStatsRow:
    user_id: uuid.UUID
    full_name: str | None
    email: str
    surveys: int
    average: float | None
    median: float | None

    @property
    def label(self) -> str:
        name = (self.full_name or "").strip()
        return name or self.email


def expert_totals(session: Session) -> ExpertTotals:
    """Surveys, expert-survey pairs, and recommendation rows by group=expert."""
    pair = tuple_(
        col(SessionRecommendation.user_id),
        col(SessionRecommendation.session_id),
    )
    statement = (
        select(
            func.count(func.distinct(col(SessionRecommendation.session_id))),
            func.count(func.distinct(pair)),
            func.count(),
        )
        .select_from(SessionRecommendation)
        .join(User, col(User.id) == SessionRecommendation.user_id)
        .where(User.group == UserGroup.EXPERT)
    )
    surveys, evaluations, recommendations = session.exec(statement).one()
    return ExpertTotals(
        surveys=int(surveys),
        evaluations=int(evaluations),
        recommendations=int(recommendations),
    )


def expert_rows(session: Session, *, active_only: bool) -> list[ExpertStatsRow]:
    """One row per expert. Median is percentile_cont(0.5) of per-survey counts."""
    per_session = (
        select(
            col(SessionRecommendation.user_id).label("user_id"),
            col(SessionRecommendation.session_id).label("session_id"),
            func.count().label("n"),
        )
        .join(User, col(User.id) == SessionRecommendation.user_id)
        .where(User.group == UserGroup.EXPERT)
        .group_by(
            col(SessionRecommendation.user_id),
            col(SessionRecommendation.session_id),
        )
        .subquery()
    )
    per_user = (
        select(
            per_session.c.user_id,
            func.count().label("surveys"),
            func.sum(per_session.c.n).label("recommendations"),
            func.percentile_cont(0.5)
            .within_group(per_session.c.n.asc())
            .label("median"),
        )
        .group_by(per_session.c.user_id)
        .subquery()
    )
    surveys = func.coalesce(per_user.c.surveys, 0)
    statement = (
        select(  # type: ignore[call-overload]  # ty: ignore[no-matching-overload]
            User.id,
            User.full_name,
            User.email,
            surveys,
            per_user.c.recommendations,
            per_user.c.median,
        )
        .outerjoin(per_user, per_user.c.user_id == User.id)
        .where(User.group == UserGroup.EXPERT)
        .order_by(surveys.desc(), col(User.email).asc())
    )
    if active_only:
        statement = statement.where(per_user.c.surveys > 0)
    rows: list[ExpertStatsRow] = []
    found = session.exec(statement)
    for user_id, full_name, email, survey_count, recommendation_count, median in found:
        count = int(survey_count)
        average = None if count == 0 else float(recommendation_count) / count
        rows.append(
            ExpertStatsRow(
                user_id=user_id,
                full_name=full_name,
                email=email,
                surveys=count,
                average=average,
                median=None if median is None else float(median),
            )
        )
    return rows
