from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ApprovalTask(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    evidence_event_ref: str = Field(index=True)
    patient_case_id: Optional[str] = Field(default=None, index=True)
    referral_episode_id: Optional[str] = Field(default=None, index=True)
    status: str = Field(default="pending", index=True)
    required_role: str = "clinical_director_or_ops_manager"
    reason: str
    risk_level: str = "amber"
    source_module: str = "evidence"
    requested_by: str = "system"
    requested_at: datetime = Field(default_factory=utc_now, index=True)
    decided_by: Optional[str] = None
    decided_by_role: Optional[str] = None
    decision_note: Optional[str] = None
    decided_at: Optional[datetime] = None
