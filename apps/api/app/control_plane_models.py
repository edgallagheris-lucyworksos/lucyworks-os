from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AccountableHandover(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    handover_ref: str = Field(index=True)
    patient_case_id: Optional[str] = Field(default=None, index=True)
    referral_episode_id: str = Field(index=True)
    from_actor: str
    from_role: str
    to_actor: Optional[str] = None
    to_role: str
    status: str = Field(default="pending", index=True)
    summary: str
    clinical_risks_json: Optional[str] = None
    outstanding_actions_json: Optional[str] = None
    escalation_threshold: Optional[str] = None
    due_at: Optional[datetime] = Field(default=None, index=True)
    accepted_by: Optional[str] = None
    accepted_by_role: Optional[str] = None
    accepted_at: Optional[datetime] = None
    decision_note: Optional[str] = None
    evidence_event_ref: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now, index=True)


class ComplianceControl(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    control_ref: str = Field(index=True)
    premises_ref: str = Field(default="default-premises", index=True)
    domain: str = Field(index=True)
    title: str
    requirement_source: Optional[str] = None
    responsible_role: str
    responsible_actor: Optional[str] = None
    evidence_required_json: Optional[str] = None
    status: str = Field(default="not_assessed", index=True)
    risk_level: str = Field(default="amber", index=True)
    review_frequency_days: int = 90
    next_review_at: Optional[datetime] = Field(default=None, index=True)
    last_reviewed_at: Optional[datetime] = None
    corrective_action: Optional[str] = None
    evidence_event_ref: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now, index=True)


class ServiceAvailability(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    service_ref: str = Field(index=True)
    premises_ref: str = Field(default="default-premises", index=True)
    department: str = Field(index=True)
    service_name: str
    declared_capability: str = "available"
    operational_status: str = Field(default="available", index=True)
    accepting_referrals: bool = True
    staffing_ready: bool = True
    equipment_ready: bool = True
    consumables_ready: bool = True
    limiting_reason: Optional[str] = None
    effective_from: datetime = Field(default_factory=utc_now, index=True)
    expected_restore_at: Optional[datetime] = None
    updated_by: str = "system"
    evidence_event_ref: Optional[str] = None
    updated_at: datetime = Field(default_factory=utc_now, index=True)


class AIModelRegistration(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    model_ref: str = Field(index=True)
    provider: str
    model_name: str
    model_version: str
    purpose: str
    risk_class: str = Field(default="administrative", index=True)
    status: str = Field(default="draft", index=True)
    approved_roles_json: Optional[str] = None
    permitted_data_json: Optional[str] = None
    prohibited_data_json: Optional[str] = None
    data_location: Optional[str] = None
    retention_policy: Optional[str] = None
    training_use_status: str = "prohibited"
    human_review_rule: str = "required"
    known_limitations: Optional[str] = None
    validation_summary: Optional[str] = None
    fallback_process: Optional[str] = None
    accountable_owner: str
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    next_review_at: Optional[datetime] = Field(default=None, index=True)
    evidence_event_ref: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now, index=True)


class CriticalResultAcknowledgement(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    result_ref: str = Field(index=True)
    patient_case_id: Optional[str] = Field(default=None, index=True)
    referral_episode_id: str = Field(index=True)
    result_type: str
    severity: str = Field(default="red", index=True)
    summary: str
    status: str = Field(default="awaiting_acknowledgement", index=True)
    assigned_to: str
    assigned_role: str
    due_at: Optional[datetime] = Field(default=None, index=True)
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None
    action_taken: Optional[str] = None
    evidence_event_ref: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now, index=True)
