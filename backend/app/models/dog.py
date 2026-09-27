import uuid
from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import Index, Text
from sqlmodel import Field, SQLModel

from app.models.base import UUID_PK_KWARGS, CreatedAtMixin, TimestampMixin


class DogStatus(StrEnum):
    SHELTER = "shelter"
    HOME = "home"
    BACK_SHELTER = "back_shelter"
    OVEREXPOSURE = "overexposure"
    UNKNOWN = "unknown"


class PlacementCode(StrEnum):
    SHELTER_STARTED = "shelter_started"
    HOME_STARTED = "home_started"
    BACK_SHELTER = "back_shelter"
    OVEREXPOSURE_STARTED = "overexposure_started"


class Shelter(TimestampMixin, SQLModel, table=True):
    __tablename__ = "shelters"  # pyright: ignore[reportAssignmentType]

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        sa_column_kwargs=UUID_PK_KWARGS,
    )
    name: str = Field(sa_type=Text)
    description: str | None = Field(default=None, sa_type=Text)
    address: str | None = Field(default=None, sa_type=Text)
    contact_info: str | None = Field(default=None, sa_type=Text)


class Owner(TimestampMixin, SQLModel, table=True):
    __tablename__ = "owners"  # pyright: ignore[reportAssignmentType]

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        sa_column_kwargs=UUID_PK_KWARGS,
    )
    name: str = Field(sa_type=Text)
    email: str | None = Field(default=None, max_length=255, unique=True)
    phone: str | None = Field(default=None, max_length=64)
    contact: str | None = Field(default=None, max_length=255)


class Dog(TimestampMixin, SQLModel, table=True):
    __tablename__ = "dogs"  # pyright: ignore[reportAssignmentType]
    __table_args__ = (
        Index("ix_dogs_shelter_id", "shelter_id"),
        Index("ix_dogs_owner_id", "owner_id"),
        Index("ix_dogs_assigned_volunteer_id", "assigned_volunteer_id"),
        Index("ix_dogs_created_by_id", "created_by_id"),
    )

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        sa_column_kwargs=UUID_PK_KWARGS,
    )
    name: str = Field(sa_type=Text)
    sex: str | None = Field(default=None, sa_type=Text)
    neutered: bool | None = None
    status: DogStatus = Field(default=DogStatus.UNKNOWN, sa_type=Text)
    description: str | None = Field(default=None, sa_type=Text)
    shelter_id: uuid.UUID | None = Field(
        default=None, foreign_key="shelters.id", ondelete="RESTRICT"
    )
    assigned_volunteer_id: uuid.UUID | None = Field(
        default=None, foreign_key="users.id", ondelete="RESTRICT"
    )
    owner_id: uuid.UUID | None = Field(
        default=None, foreign_key="owners.id", ondelete="RESTRICT"
    )
    birthday: date | None = None
    status_at: date | None = None
    breed: str | None = Field(default=None, sa_type=Text)
    mixed: bool | None = None
    created_by_id: uuid.UUID | None = Field(
        default=None, foreign_key="users.id", ondelete="RESTRICT"
    )


class DogChip(CreatedAtMixin, SQLModel, table=True):
    __tablename__ = "dog_chips"  # pyright: ignore[reportAssignmentType]
    __table_args__ = (Index("ix_dog_chips_dog_id", "dog_id"),)

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        sa_column_kwargs=UUID_PK_KWARGS,
    )
    dog_id: uuid.UUID = Field(foreign_key="dogs.id", ondelete="RESTRICT")
    system: str = Field(sa_type=Text)
    code: str = Field(sa_type=Text)


class PlacementEvent(CreatedAtMixin, SQLModel, table=True):
    __tablename__ = "placement_events"  # pyright: ignore[reportAssignmentType]
    __table_args__ = (Index("ix_placement_events_dog_id", "dog_id"),)

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        sa_column_kwargs=UUID_PK_KWARGS,
    )
    dog_id: uuid.UUID = Field(foreign_key="dogs.id", ondelete="RESTRICT")
    code: PlacementCode = Field(sa_type=Text)


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
    status: DogStatus
    description: str | None = None
    shelter_id: uuid.UUID | None = None
    assigned_volunteer_id: uuid.UUID | None = None
    owner_id: uuid.UUID | None = None
    birthday: date | None = None
    status_at: date | None = None
    breed: str | None = None
    mixed: bool | None = None
    created_by_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime


class DogsPublic(SQLModel):
    data: list[DogPublic]
    count: int
