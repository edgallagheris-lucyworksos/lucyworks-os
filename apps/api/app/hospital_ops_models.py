from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class HospitalPremises(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    premises_ref: str = Field(index=True)
    name: str
    timezone_name: str = "Europe/London"
    status: str = Field(default="active", index=True)
    created_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now, index=True)


class OperationalArea(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    area_ref: str = Field(index=True)
    premises_ref: str = Field(index=True)
    name: str
    area_type: str = Field(index=True)
    department: str = Field(index=True)
    capacity: int = 1
    turnover_minutes: int = 0
    required_skills_json: Optional[str] = None
    compatible_procedures_json: Optional[str] = None
    equipment_refs_json: Optional[str] = None
    active: bool = True
    created_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now, index=True)


class CanonicalEpisodeState(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    episode_ref: str = Field(index=True)
    patient_ref: Optional[str] = Field(default=None, index=True)
    patient_name: str
    premises_ref: str = Field(index=True)
    service_line: str = Field(default="referral", index=True)
    urgency: str = Field(default="routine", index=True)
    phase: str = Field(default="referral_received", index=True)
    status: str = Field(default="active", index=True)
    owner_role: str = "reception"
    owner_subject: Optional[str] = Field(default=None, index=True)
    current_area_ref: Optional[str] = Field(default=None, index=True)
    next_action: Optional[str] = None
    gates_json: Optional[str] = None
    flags_json: Optional[str] = None
    version: int = 1
    last_command_ref: Optional[str] = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now, index=True)


class OperationalBlock(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    block_ref: str = Field(index=True)
    premises_ref: str = Field(index=True)
    operational_date: date = Field(index=True)
    episode_ref: Optional[str] = Field(default=None, index=True)
    patient_ref: Optional[str] = Field(default=None, index=True)
    patient_name: Optional[str] = Field(default=None, index=True)
    procedure_ref: Optional[str] = Field(default=None, index=True)
    procedure_name: str
    block_type: str = Field(default="procedure", index=True)
    area_ref: str = Field(index=True)
    area_name: str
    starts_at: datetime = Field(index=True)
    ends_at: datetime = Field(index=True)
    status: str = Field(default="planned", index=True)
    risk_level: str = Field(default="amber", index=True)
    priority: int = 50
    lead_staff_ref: Optional[str] = Field(default=None, index=True)
    lead_staff_name: Optional[str] = None
    lead_staff_role: Optional[str] = None
    assistant_refs_json: Optional[str] = None
    equipment_refs_json: Optional[str] = None
    required_skills_json: Optional[str] = None
    dependency_refs_json: Optional[str] = None
    blockers_json: Optional[str] = None
    gates_json: Optional[str] = None
    pharmacy_refs_json: Optional[str] = None
    external_refs_json: Optional[str] = None
    notes: Optional[str] = None
    version: int = 1
    last_command_ref: Optional[str] = Field(default=None, index=True)
    updated_by_subject: str = "system"
    updated_by_name: str = "system"
    updated_by_role: str = "system"
    updated_by_auth_source: str = "system"
    created_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now, index=True)


class OperationalDependency(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    dependency_ref: str = Field(index=True)
    premises_ref: str = Field(index=True)
    predecessor_block_ref: str = Field(index=True)
    successor_block_ref: str = Field(index=True)
    dependency_type: str = Field(default="finish_to_start", index=True)
    lag_minutes: int = 0
    hard_constraint: bool = True
    created_at: datetime = Field(default_factory=utc_now, index=True)


class OperationalCommand(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    command_ref: str = Field(index=True)
    command_type: str = Field(index=True)
    target_type: str = Field(index=True)
    target_ref: str = Field(index=True)
    expected_version: Optional[int] = None
    request_json: str
    result_json: Optional[str] = None
    status: str = Field(default="received", index=True)
    idempotency_key: Optional[str] = Field(default=None, index=True)
    actor_subject: str = Field(index=True)
    actor_name: str
    actor_role: str = Field(index=True)
    auth_source: str
    evidence_event_ref: Optional[str] = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=utc_now, index=True)
    completed_at: Optional[datetime] = Field(default=None, index=True)


class OperationalConflict(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    conflict_ref: str = Field(index=True)
    premises_ref: str = Field(index=True)
    operational_date: date = Field(index=True)
    conflict_type: str = Field(index=True)
    severity: str = Field(index=True)
    status: str = Field(default="open", index=True)
    primary_block_ref: Optional[str] = Field(default=None, index=True)
    related_refs_json: Optional[str] = None
    explanation: str
    options_json: Optional[str] = None
    fingerprint: str = Field(index=True)
    detected_at: datetime = Field(default_factory=utc_now, index=True)
    resolved_at: Optional[datetime] = None
    resolution_command_ref: Optional[str] = Field(default=None, index=True)


class BoardChangeEvent(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    event_ref: str = Field(index=True)
    premises_ref: str = Field(index=True)
    operational_date: date = Field(index=True)
    event_type: str = Field(index=True)
    entity_type: str
    entity_ref: str = Field(index=True)
    entity_version: Optional[int] = None
    command_ref: Optional[str] = Field(default=None, index=True)
    payload_json: str
    created_at: datetime = Field(default_factory=utc_now, index=True)


class ScenarioRun(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    run_ref: str = Field(index=True)
    scenario_name: str
    premises_ref: str = Field(index=True)
    operational_date: date = Field(index=True)
    seed: int
    status: str = Field(default="running", index=True)
    committed: bool = False
    configuration_json: str
    metrics_json: Optional[str] = None
    created_by_subject: str = Field(index=True)
    created_at: datetime = Field(default_factory=utc_now, index=True)
    completed_at: Optional[datetime] = None


class ImportBatch(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    batch_ref: str = Field(index=True)
    source_type: str = Field(index=True)
    source_name: str
    premises_ref: str = Field(index=True)
    status: str = Field(default="preview", index=True)
    row_count: int = 0
    accepted_count: int = 0
    rejected_count: int = 0
    source_hash: str = Field(index=True)
    mapping_json: Optional[str] = None
    summary_json: Optional[str] = None
    created_by_subject: str = Field(index=True)
    created_at: datetime = Field(default_factory=utc_now, index=True)
    committed_at: Optional[datetime] = None


class ImportReconciliationItem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    item_ref: str = Field(index=True)
    batch_ref: str = Field(index=True)
    row_number: int
    status: str = Field(default="unmatched", index=True)
    issue_type: str = Field(index=True)
    detail: str
    source_record_json: str
    suggested_match_json: Optional[str] = None
    resolved_by_subject: Optional[str] = Field(default=None, index=True)
    resolution_json: Optional[str] = None
    created_at: datetime = Field(default_factory=utc_now, index=True)
    resolved_at: Optional[datetime] = None
