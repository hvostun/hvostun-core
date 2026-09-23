import uuid
from datetime import datetime

from pydantic import EmailStr
from sqlalchemy import Column, DateTime, String, Text, UniqueConstraint
from sqlmodel import Field, SQLModel

from app.models.base import TimestampMixin


class UserBase(SQLModel):
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    is_active: bool = True
    is_superuser: bool = False
    full_name: str | None = Field(default=None, max_length=255)
    group: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=64)
    contact: str | None = Field(default=None, max_length=255)


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)


class UserUpdate(SQLModel):
    email: EmailStr | None = Field(default=None, max_length=255)
    is_active: bool | None = None
    is_superuser: bool | None = None
    full_name: str | None = Field(default=None, max_length=255)
    group: str | None = None
    phone: str | None = Field(default=None, max_length=64)
    contact: str | None = Field(default=None, max_length=255)
    password: str | None = Field(default=None, min_length=8, max_length=128)


class UserUpdateMe(SQLModel):
    full_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = Field(default=None, max_length=255)


class UpdatePassword(SQLModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class User(UserBase, TimestampMixin, table=True):
    __tablename__ = "users"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    hashed_password: str
    group: str | None = Field(
        default=None,
        sa_column=Column("group", String(255), nullable=True),
    )


class UserPublic(UserBase):
    id: uuid.UUID
    created_at: datetime | None = None
    updated_at: datetime | None = None


class UsersPublic(SQLModel):
    data: list[UserPublic]
    count: int


class Message(SQLModel):
    message: str


class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"


class TokenPayload(SQLModel):
    sub: str | None = None


class NewPassword(SQLModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


class Consent(SQLModel, table=True):
    __tablename__ = "consents"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "type", "version", name="uq_consents_user_type_version"
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", ondelete="CASCADE")
    type: str = Field(sa_type=Text)
    accepted_at: datetime = Field(sa_type=DateTime(timezone=True))  # type: ignore[call-overload]
    version: str = Field(sa_type=Text)
