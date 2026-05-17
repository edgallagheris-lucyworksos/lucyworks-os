from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DischargeBlocker(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    episode_id: int = Field(foreign_key="episode.id")
    blocker_type: str
    detail: str
    owner_role: str = "clinician"
    status: str = "open"
    severity: str = "amber"
    created_at: datetime = Field(default_factory=utc_now)
    resolved_at: Optional[datetime] = None
    resolution_note: Optional[str] = None


class OccupancyRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    space_id: str
    space_type: str
    episode_id: Optional[int] = Field(default=None, foreign_key="episode.id")
    occupied_from: datetime = Field(default_factory=utc_now)
    expected_release: Optional[datetime] = None
    status: str = "occupied"
    created_at: datetime = Field(default_factory=utc_now)
    released_at: Optional[datetime] = None


class SeverityGate(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    episode_id: Optional[int] = Field(default=None, foreign_key="episode.id")
    gate_name: str
    target_entity_type: str
    target_entity_id: Optional[int] = None
    severity: str = "MINOR"
    system_action: str = "Log and proceed."
    reasons: str = ""
    status: str = "open"
    reviewer_name: Optional[str] = None
    override_reason: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)
    resolved_at: Optional[datetime] = None


class StaffAssignmentRisk(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    episode_id: Optional[int] = Field(default=None, foreign_key="episode.id")
    staff_member_id: Optional[int] = Field(default=None, foreign_key="staffmember.id")
    role_required: str
    required_skills: str = ""
    matched_skills: str = ""
    skill_match_count: int = 0
    load_ratio: float = 0.0
    rota_risk: str = "LOW"
    status: str = "proposed"
    reviewer_name: Optional[str] = None
    override_reason: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)
    resolved_at: Optional[datetime] = None


class MessagingTemplate(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    message_type: str
    purpose: str
    template_text: str = ""
    active: bool = True


class SpeechTarget(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    target: str
    purpose: str
    route_to_entity: str
    active: bool = True


class ComplianceGate(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    gate_type: str
    entity_type: str
    entity_id: Optional[int] = None
    status: str = "open"
    detail: str
    owner_role: str = "ops_manager"
    created_at: datetime = Field(default_factory=utc_now)
    resolved_at: Optional[datetime] = None
