from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ReadinessControl(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    control_ref: str = Field(index=True, sa_column_kwargs={"unique": True})
    category: str = Field(index=True)
    title: str
    description: str
    required: bool = True
    status: str = Field(default="not_started", index=True)
    owner_role: str = Field(default="ops_manager", index=True)
    evidence_summary: Optional[str] = None
    evidence_ref: Optional[str] = Field(default=None, index=True)
    verified_by_subject: Optional[str] = Field(default=None, index=True)
    verified_by_name: Optional[str] = None
    verified_at: Optional[datetime] = Field(default=None, index=True)
    expires_at: Optional[datetime] = Field(default=None, index=True)
    waiver_reason: Optional[str] = None
    version: int = 1
    created_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now, index=True)


class ReadinessEvidence(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    evidence_ref: str = Field(index=True, sa_column_kwargs={"unique": True})
    control_ref: str = Field(index=True)
    evidence_type: str = Field(index=True)
    summary: str
    source_ref: Optional[str] = Field(default=None, index=True)
    payload_hash: Optional[str] = Field(default=None, index=True)
    recorded_by_subject: str = Field(index=True)
    recorded_by_name: str
    recorded_at: datetime = Field(default_factory=utc_now, index=True)


class SecurityAssessmentRun(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    run_ref: str = Field(index=True, sa_column_kwargs={"unique": True})
    environment_name: str = Field(default="unknown", index=True)
    status: str = Field(default="running", index=True)
    score: int = 0
    passed_count: int = 0
    failed_count: int = 0
    warning_count: int = 0
    checks_json: str = "[]"
    created_by_subject: str = Field(index=True)
    created_at: datetime = Field(default_factory=utc_now, index=True)
    completed_at: Optional[datetime] = Field(default=None, index=True)


class PilotRun(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    run_ref: str = Field(index=True, sa_column_kwargs={"unique": True})
    phase: str = Field(index=True)
    service_line: str = Field(default="referral", index=True)
    premises_ref: str = Field(default="default-premises", index=True)
    status: str = Field(default="planned", index=True)
    accountable_owner: str
    success_criteria_json: str = "{}"
    metrics_json: str = "{}"
    blockers_json: str = "[]"
    started_at: Optional[datetime] = Field(default=None, index=True)
    ended_at: Optional[datetime] = Field(default=None, index=True)
    approved_by_subject: Optional[str] = Field(default=None, index=True)
    approval_note: Optional[str] = None
    created_by_subject: str = Field(index=True)
    created_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now, index=True)


class PilotObservation(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    observation_ref: str = Field(index=True, sa_column_kwargs={"unique": True})
    run_ref: str = Field(index=True)
    severity: str = Field(default="amber", index=True)
    category: str = Field(index=True)
    summary: str
    expected_behaviour: Optional[str] = None
    actual_behaviour: Optional[str] = None
    owner_role: str = Field(default="ops_manager", index=True)
    status: str = Field(default="open", index=True)
    resolution: Optional[str] = None
    recorded_by_subject: str = Field(index=True)
    created_at: datetime = Field(default_factory=utc_now, index=True)
    resolved_at: Optional[datetime] = Field(default=None, index=True)
