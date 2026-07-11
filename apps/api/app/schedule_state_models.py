from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ScheduleStateBlock(SQLModel, table=True):
    id: str = Field(primary_key=True)
    time: str
    lane: str
    what: str
    who: str
    where: str
    how: str
    status: str = "amber"
    blocker: str = "none"
    next: str = "continue planned flow"
    route: str = "/hospital-board"
    subject: Optional[str] = None
    duration_minutes: Optional[int] = None
    generated_from: Optional[str] = None
    episode_ref: Optional[str] = None
    assigned_role: Optional[str] = None
    assigned_staff_id: Optional[int] = None
    assigned_staff_name: Optional[str] = None
    resource_id: Optional[str] = None
    resource_name: Optional[str] = None
    consent_status: Optional[str] = None
    estimate_status: Optional[str] = None
    insurance_status: Optional[str] = None
    pharmacy_ready: Optional[bool] = None
    owner_updated: Optional[bool] = None
    referring_vet_report_sent: Optional[bool] = None
    discharge_clear: Optional[bool] = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class ScheduleStateEvent(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    block_id: str
    action: str
    actor: str = "system"
    reason: Optional[str] = None
    before_json: str = ""
    after_json: str = ""
    created_at: datetime = Field(default_factory=utc_now)
