import uuid
from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import Text
from sqlmodel import Field, SQLModel

from app.models.base import CreatedAtMixin, TimestampMixin


class DogStatus(StrEnum):
    SHELTER = "shelter"
    HOME = "home"
    OVEREXPOSURE = "overexposure"
    UNKNOWN = "unknown"


class PlacementCode(StrEnum):
    SHELTER_STARTED = "shelter_started"
    HOME_STARTED = "home_started"
    OVEREXPOSURE_STARTED = "overexposure_started"
    UNKNOWN = "unknown"


class Shelter(TimestampMixin, SQLModel, table=True):
    __tablename__ = "shelters"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(sa_type=Text)
    description: str | None = Field(default=None, sa_type=Text)
    address: str | None = Field(default=None, sa_type=Text)
    contact_info: str | None = Field(default=None, sa_type=Text)


class Owner(TimestampMixin, SQLModel, table=True):
    __tablename__ = "owners"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(sa_type=Text)
    email: str | None = Field(default=None, max_length=255, unique=True)
    phone: str | None = Field(default=None, max_length=64)
    contact: str | None = Field(default=None, max_length=255)


class Dog(TimestampMixin, SQLModel, table=True):
    __tablename__ = "dogs"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(sa_type=Text)
    sex: str | None = Field(default=None, sa_type=Text)
    neutered: bool | None = None
    status: str = Field(default=DogStatus.UNKNOWN, sa_type=Text)
    description: str | None = Field(default=None, sa_type=Text)
    shelter_id: uuid.UUID | None = Field(default=None, foreign_key="shelters.id")
    assigned_volunteer_id: uuid.UUID | None = Field(
        default=None, foreign_key="users.id"
    )
    owner_id: uuid.UUID | None = Field(default=None, foreign_key="owners.id")
    birthday: date | None = None
    adopted_at: date | None = None
    breed: str | None = Field(default=None, sa_type=Text)
    mixed: bool | None = None
    created_by_id: uuid.UUID | None = Field(default=None, foreign_key="users.id")


class DogChip(CreatedAtMixin, SQLModel, table=True):
    __tablename__ = "dog_chips"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    dog_id: uuid.UUID = Field(foreign_key="dogs.id", ondelete="CASCADE")
    system: str = Field(sa_type=Text)
    code: str = Field(sa_type=Text)


class PlacementEvent(CreatedAtMixin, SQLModel, table=True):
    __tablename__ = "placement_events"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    dog_id: uuid.UUID = Field(foreign_key="dogs.id", ondelete="CASCADE")
    code: str = Field(sa_type=Text)


class OwnerPublic(SQLModel):
    id: uuid.UUID
    name: str
    email: str | None = None
    phone: str | None = None
    contact: str | None = None
    created_at: datetime
    updated_at: datetime


class OwnersPublic(SQLModel):
    data: list[OwnerPublic]
    count: int


class DogPublic(SQLModel):
    id: uuid.UUID
    name: str
    sex: str | None = None
    neutered: bool | None = None
    status: str
    description: str | None = None
    shelter_id: uuid.UUID | None = None
    assigned_volunteer_id: uuid.UUID | None = None
    owner_id: uuid.UUID | None = None
    birthday: date | None = None
    adopted_at: date | None = None
    breed: str | None = None
    mixed: bool | None = None
    created_by_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime


class DogsPublic(SQLModel):
    data: list[DogPublic]
    count: int
