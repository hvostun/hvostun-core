import uuid
from datetime import date
from enum import StrEnum

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
    name: str
    description: str | None = None
    address: str | None = None
    contact_info: str | None = None


class Dog(TimestampMixin, SQLModel, table=True):
    __tablename__ = "dogs"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str
    sex: str | None = None
    neutered: bool | None = None
    status: str = Field(default=DogStatus.UNKNOWN)
    description: str | None = None
    shelter_id: uuid.UUID | None = Field(default=None, foreign_key="shelters.id")
    assigned_volunteer_id: uuid.UUID | None = Field(
        default=None, foreign_key="users.id"
    )
    owner_id: uuid.UUID | None = Field(default=None, foreign_key="users.id")
    birthday: date | None = None
    adopted_at: date | None = None
    breed: str | None = None
    mixed: bool | None = None
    created_by_id: uuid.UUID | None = Field(default=None, foreign_key="users.id")


class DogChip(CreatedAtMixin, SQLModel, table=True):
    __tablename__ = "dog_chips"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    dog_id: uuid.UUID = Field(foreign_key="dogs.id", ondelete="CASCADE")
    system: str
    code: str


class PlacementEvent(CreatedAtMixin, SQLModel, table=True):
    __tablename__ = "placement_events"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    dog_id: uuid.UUID = Field(foreign_key="dogs.id", ondelete="CASCADE")
    code: str
