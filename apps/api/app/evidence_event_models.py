from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class EvidenceEvent(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    event_ref: str = Field(index=True)
    event_type: str = Field(index=True)
    patient_case_id: Optional[str] = Field(default=None, index=True)
    referral_episode_id: Optional[str] = Field(default=None, index=True)
    schedule_block_id: Optional[str] = Field(default=None, index=True)
    actor_id: Optional[str] = None
    actor_name: str = "system"
    actor_role: str = "system"
    professional_role: Optional[str] = None
    action: str
    previous_state_json: Optional[str] = None
    new_state_json: Optional[str] = None
    reason: Optional[str] = None
    justification: Optional[str] = None
    evidence_links_json: Optional[str] = None
    alternatives_discussed_json: Optional[str] = None
    client_authorisation_json: Optional[str] = None
    ai_system: Optional[str] = None
    ai_model: Optional[str] = None
    ai_prompt_ref: Optional[str] = None
    ai_output_ref: Optional[str] = None
    ai_confidence: Optional[str] = None
    human_reviewer: Optional[str] = None
    human_review_status: str = "not_required"
    supervisor_required: bool = False
    supervisor_name: Optional[str] = None
    supervisor_approval_status: str = "not_required"
    override_reason: Optional[str] = None
    compliance_domain: str = "operations"
    risk_level: str = "amber"
    source_module: str = "lucyworks"
    immutable: bool = True
    created_at: datetime = Field(default_factory=utc_now, index=True)


class EstimateVersion(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    estimate_ref: str = Field(index=True)
    patient_case_id: str = Field(index=True)
    referral_episode_id: Optional[str] = Field(default=None, index=True)
    version: int = 1
    status: str = "draft"
    lower_amount: Optional[float] = None
    upper_amount: Optional[float] = None
    currency: str = "GBP"
    assumptions_json: Optional[str] = None
    itemised_lines_json: Optional[str] = None
    excluded_items_json: Optional[str] = None
    insurance_assumptions_json: Optional[str] = None
    alternatives_json: Optional[str] = None
    client_notified_at: Optional[datetime] = None
    client_decision: str = "not_recorded"
    emergency_authority: bool = False
    clinician_justification: Optional[str] = None
    created_by: str = "system"
    created_at: datetime = Field(default_factory=utc_now, index=True)


class ConsentRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    consent_ref: str = Field(index=True)
    patient_case_id: str = Field(index=True)
    referral_episode_id: Optional[str] = Field(default=None, index=True)
    consent_type: str = "procedure"
    status: str = "pending"
    scope: str = "not_recorded"
    risks_discussed_json: Optional[str] = None
    alternatives_discussed_json: Optional[str] = None
    cost_discussed: bool = False
    estimate_ref: Optional[str] = None
    client_authorised_by: Optional[str] = None
    client_authorised_at: Optional[datetime] = None
    recorded_by: str = "system"
    witness: Optional[str] = None
    evidence_event_ref: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now, index=True)
