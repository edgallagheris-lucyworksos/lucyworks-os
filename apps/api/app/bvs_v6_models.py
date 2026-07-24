from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Optional

from sqlalchemy import Column, JSON, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class HospitalConfigurationRecord(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("premises_ref", "entity_type", "entity_ref", name="uq_hospital_config_entity"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    premises_ref: str = Field(index=True)
    entity_type: str = Field(index=True)
    entity_ref: str = Field(index=True)
    name: str
    attributes: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    operational_status: str = "draft"
    verification_status: str = "unverified"
    authoritative_source_ref: Optional[str] = None
    version: int = 1
    updated_by_actor_id: str
    updated_by_actor_name: str
    updated_by_actor_role: str
    updated_at: datetime = Field(default_factory=utc_now)


class ConfigurationClaim(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("claim_ref", name="uq_configuration_claim_ref"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    claim_ref: str = Field(index=True)
    premises_ref: str = Field(index=True)
    entity_type: str = Field(index=True)
    entity_ref: str = Field(index=True)
    field_name: str = Field(index=True)
    claimed_value: Any = Field(default=None, sa_column=Column(JSON, nullable=True))
    source_type: str
    source_ref: Optional[str] = None
    source_url: Optional[str] = None
    observed_at: Optional[datetime] = None
    confidence: str = "unknown"
    status: str = "proposed"
    notes: Optional[str] = None
    version: int = 1
    created_by_actor_id: str
    created_by_actor_name: str
    created_at: datetime = Field(default_factory=utc_now)
    reviewed_by_actor_id: Optional[str] = None
    reviewed_by_actor_name: Optional[str] = None
    reviewed_at: Optional[datetime] = None


class ConfigurationVerificationTask(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("task_ref", name="uq_configuration_verification_task_ref"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    task_ref: str = Field(index=True)
    premises_ref: str = Field(index=True)
    category: str = Field(index=True)
    question: str
    why_it_matters: str
    requested_evidence: str
    accountable_role: str
    priority: str = "amber"
    status: str = "open"
    linked_entity_type: Optional[str] = None
    linked_entity_ref: Optional[str] = None
    linked_claim_refs: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    answer: Optional[str] = None
    evidence_refs: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    version: int = 1
    created_at: datetime = Field(default_factory=utc_now)
    answered_by_actor_id: Optional[str] = None
    answered_by_actor_name: Optional[str] = None
    answered_by_actor_role: Optional[str] = None
    answered_at: Optional[datetime] = None


class WorkforceProfile(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("premises_ref", "staff_ref", name="uq_workforce_staff_ref"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    premises_ref: str = Field(index=True)
    staff_ref: str = Field(index=True)
    display_name: str
    employment_status: str = "active"
    primary_role_ref: str = Field(index=True)
    department_ref: str = Field(index=True)
    grade_or_training_level: Optional[str] = None
    registration_body: Optional[str] = None
    registration_number: Optional[str] = None
    contracted_hours_weekly: Optional[float] = None
    maximum_safe_hours_weekly: Optional[float] = None
    supervisor_staff_ref: Optional[str] = None
    on_call_eligible: bool = False
    source_status: str = "draft"
    version: int = 1
    updated_by_actor_id: str
    updated_by_actor_name: str
    updated_at: datetime = Field(default_factory=utc_now)


class WorkforceCompetency(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("premises_ref", "staff_ref", "competency_ref", "scope_ref", name="uq_workforce_competency"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    premises_ref: str = Field(index=True)
    staff_ref: str = Field(index=True)
    competency_ref: str = Field(index=True)
    scope_ref: str = "hospital"
    level: str = "supervised"
    status: str = "provisional"
    evidence_summary: Optional[str] = None
    valid_from: Optional[date] = None
    valid_until: Optional[date] = None
    verified_by_actor_id: Optional[str] = None
    verified_by_actor_name: Optional[str] = None
    verified_at: Optional[datetime] = None
    version: int = 1


class CoverageRequirement(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("premises_ref", "requirement_ref", name="uq_coverage_requirement"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    premises_ref: str = Field(index=True)
    requirement_ref: str = Field(index=True)
    service_ref: str = Field(index=True)
    area_ref: Optional[str] = None
    role_ref: str
    competency_ref: Optional[str] = None
    day_type: str = "all"
    starts_at_local: str = "00:00"
    ends_at_local: str = "23:59"
    minimum_count: int = 1
    escalation_role: str = "ops_manager"
    verification_status: str = "unverified"
    version: int = 1


class ReferralIntake(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("referral_ref", name="uq_referral_intake_ref"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    referral_ref: str = Field(index=True)
    premises_ref: str = Field(index=True)
    received_at: datetime = Field(default_factory=utc_now)
    source_channel: str = "portal"
    urgency: str = "routine"
    referring_practice: str
    referring_vet: Optional[str] = None
    practice_contact: Optional[str] = None
    patient_name: str
    species: str
    owner_name: str
    owner_contact: Optional[str] = None
    requested_service_ref: Optional[str] = None
    presenting_problem: str
    history_summary: Optional[str] = None
    insurance_status: str = "unknown"
    attachment_manifest: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    required_information: dict[str, bool] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    missing_information: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    status: str = "received"
    decision: Optional[str] = None
    decision_reason: Optional[str] = None
    assigned_role: str = "referral_coordinator"
    assigned_actor_id: Optional[str] = None
    assigned_actor_name: Optional[str] = None
    response_due_at: Optional[datetime] = None
    version: int = 1
    created_by_actor_id: str
    created_by_actor_name: str
    updated_at: datetime = Field(default_factory=utc_now)


class ReferralIntakeEvent(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    referral_ref: str = Field(index=True)
    event_type: str
    previous_status: Optional[str] = None
    new_status: str
    detail: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    actor_id: str
    actor_name: str
    actor_role: str
    created_at: datetime = Field(default_factory=utc_now)


class HistoricalReplayRun(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("run_ref", name="uq_historical_replay_run_ref"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    run_ref: str = Field(index=True)
    premises_ref: str = Field(index=True)
    source_date: date
    data_classification: str = "anonymised"
    status: str = "draft"
    event_count: int = 0
    metrics: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    findings: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    created_by_actor_id: str
    created_by_actor_name: str
    created_at: datetime = Field(default_factory=utc_now)
    completed_at: Optional[datetime] = None


class HistoricalReplayEvent(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("run_ref", "event_ref", name="uq_historical_replay_event"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    run_ref: str = Field(index=True)
    event_ref: str = Field(index=True)
    occurred_at: datetime
    event_type: str
    episode_ref: Optional[str] = None
    area_ref: Optional[str] = None
    staff_refs: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    payload: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
