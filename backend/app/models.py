from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    role: str
    email: str
    active: bool = True


class HospitalSection(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    section_type: str
    active: bool = True


class Room(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    section_name: str
    name: str
    room_type: str
    active: bool = True


class Patient(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    patient_name: str
    species: str
    owner_name: str
    owner_phone: Optional[str] = None
    weight_kg: Optional[float] = None


class Episode(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    episode_ref: str
    patient_id: int = Field(foreign_key="patient.id")
    status: str = "active"
    current_section_name: Optional[str] = None
    current_room_name: Optional[str] = None
    current_phase: str = "intake"
    created_at: datetime = Field(default_factory=utc_now)


class Admission(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    episode_id: int = Field(foreign_key="episode.id")
    admitted_to: str
    admitted_at: datetime = Field(default_factory=utc_now)
    status: str = "active"


class Handover(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    episode_id: int = Field(foreign_key="episode.id")
    from_owner: str
    to_owner: str
    note: str
    acknowledged: bool = False
    created_at: datetime = Field(default_factory=utc_now)


class ResultReview(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    episode_id: int = Field(foreign_key="episode.id")
    result_type: str
    review_owner: str
    status: str = "pending_review"
    reviewed_at: Optional[datetime] = None


class RoomState(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    room_name: str
    room_type: str
    department: str
    state: str
    current_episode_ref: Optional[str] = None
    next_episode_ref: Optional[str] = None
    cleaning_due_minutes: Optional[int] = None


class WorkItem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    input_type: str
    source: str
    category: str
    description: str
    urgency: str
    owner_role: str
    owner_user_id: Optional[int] = Field(default=None, foreign_key="user.id")
    section_name: Optional[str] = None
    room_name: Optional[str] = None
    patient_location_label: Optional[str] = None
    linked_patient_name: Optional[str] = None
    linked_episode_ref: Optional[str] = None
    status: str = "new"
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    due_at: Optional[datetime] = None


class AuditEvent(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    actor_name: str
    action: str
    entity_type: str
    entity_id: int
    summary: str
    created_at: datetime = Field(default_factory=utc_now)
