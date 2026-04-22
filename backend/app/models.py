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
