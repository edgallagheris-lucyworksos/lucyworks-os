from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PatientCase(SQLModel, table=True):
    id: str = Field(primary_key=True)
    patient_name: str
    species: Optional[str] = None
    breed: Optional[str] = None
    owner_name: Optional[str] = None
    referral_reason: Optional[str] = None
    risk_level: str = "amber"
    status: str = "active"
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class ReferralEpisode(SQLModel, table=True):
    id: str = Field(primary_key=True)
    patient_case_id: str = Field(index=True)
    episode_ref: str = Field(index=True)
    stage: str = "intake"
    owner_role: str = "unassigned"
    owner_name: Optional[str] = None
    current_location: Optional[str] = None
    next_action: str = "confirm referral plan"
    blocker: str = "none"
    status: str = "active"
    consent_status: Optional[str] = None
    estimate_status: Optional[str] = None
    insurance_status: Optional[str] = None
    pharmacy_ready: Optional[bool] = None
    owner_updated: Optional[bool] = None
    referring_vet_report_sent: Optional[bool] = None
    discharge_clear: Optional[bool] = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class PatientWorkflowEvent(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    episode_id: str = Field(index=True)
    patient_case_id: str = Field(index=True)
    event_type: str
    action: str
    actor: str = "system"
    note: Optional[str] = None
    source_block_id: Optional[str] = None
    at_time: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now)
