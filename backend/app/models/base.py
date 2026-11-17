from datetime import UTC, datetime

from sqlalchemy import DateTime, event, func, text
from sqlalchemy.orm import Session as SASession
from sqlmodel import Field, SQLModel

UUID_PK_KWARGS = {"server_default": text("uuid_generate_v4()")}


def get_datetime_utc() -> datetime:
    return datetime.now(UTC)


class CreatedAtMixin(SQLModel):
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore[call-overload]  # ty: ignore[invalid-argument-type]
        sa_column_kwargs={"server_default": func.now(), "nullable": False},
    )


class TimestampMixin(CreatedAtMixin):
    updated_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore[call-overload]  # ty: ignore[invalid-argument-type]
        sa_column_kwargs={
            "server_default": func.now(),
            "onupdate": get_datetime_utc,
            "nullable": False,
        },
    )


@event.listens_for(SASession, "before_flush")
def _set_timestamps(
    session: SASession, _flush_context: object, _instances: object
) -> None:
    now = get_datetime_utc()
    for obj in session.dirty:
        if isinstance(obj, TimestampMixin) and session.is_modified(
            obj, include_collections=False
        ):
            obj.updated_at = now
