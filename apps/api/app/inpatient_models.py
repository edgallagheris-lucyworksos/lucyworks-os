from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class InpatientStay(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    episode_id: int = Field(foreign_key="episode.id")
    location_room: str
    bed_label: str
    acuity: str = "routine"
    status: str = "active"
    admitted_at: datetime = Field(default_factory=utc_now)
    expected_discharge_at: Optional[datetime] = None
    overnight_required: bool = True
    obs_frequency_minutes: int = 240
    morning_review_required: bool = True
    owner_update_required: bool = True
    notes: str = ""


class ObservationTask(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    episode_id: int = Field(foreign_key="episode.id")
    inpatient_stay_id: Optional[int] = Field(default=None, foreign_key="inpatientstay.id")
    task_type: str
    detail: str
    due_at: datetime
    frequency_minutes: Optional[int] = None
    owner_role: str = "nurse"
    status: str = "due"
    escalation_required: bool = False
    created_at: datetime = Field(default_factory=utc_now)
    completed_at: Optional[datetime] = None


class MedicationDue(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    episode_id: int = Field(foreign_key="episode.id")
    inpatient_stay_id: Optional[int] = Field(default=None, foreign_key="inpatientstay.id")
    medication_name: str
    due_at: datetime
    route: str = "as prescribed"
    controlled_or_legal_status: str = "standard"
    owner_role: str = "nurse"
    status: str = "due"
    pharmacy_blocker: bool = False
    created_at: datetime = Field(default_factory=utc_now)
    completed_at: Optional[datetime] = None


class NightHandover(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    episode_id: int = Field(foreign_key="episode.id")
    inpatient_stay_id: Optional[int] = Field(default=None, foreign_key="inpatientstay.id")
    from_role: str
    to_role: str
    risk_level: str = "amber"
    summary: str
    meds_due_summary: str = ""
    obs_plan: str = ""
    morning_decision_required: str = ""
    owner_update_status: str = "due"
    acknowledged: bool = False
    created_at: datetime = Field(default_factory=utc_now)
    acknowledged_at: Optional[datetime] = None


class OvernightEvent(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    episode_id: int = Field(foreign_key="episode.id")
    inpatient_stay_id: Optional[int] = Field(default=None, foreign_key="inpatientstay.id")
    event_type: str
    severity: str
    detail: str
    action_taken: str = ""
    owner_role: str = "nurse"
    status: str = "open"
    occurred_at: datetime = Field(default_factory=utc_now)
    resolved_at: Optional[datetime] = None


class FinancialConsentStatus(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    episode_id: int = Field(foreign_key="episode.id")
    consent_status: str = "unknown"
    estimate_status: str = "unknown"
    insurance_status: str = "unknown"
    payment_status: str = "unknown"
    direct_claim_status: str = "not_applicable"
    pre_authorisation_status: str = "not_applicable"
    owner_financial_constraint: bool = False
    pharmacy_blocked: bool = False
    discharge_blocked: bool = False
    material_decision_required: bool = False
    owner_role: str = "admin"
    notes: str = ""
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
