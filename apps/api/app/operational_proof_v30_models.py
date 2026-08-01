from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Optional

from sqlalchemy import Column, JSON, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class OperationalProofRunV30(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("run_ref", name="uq_operationalproofrunv30_ref"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    run_ref: str = Field(index=True)
    organisation_ref: str = Field(index=True)
    site_ref: str = Field(index=True)
    premises_ref: str = Field(index=True)
    operational_date: date = Field(index=True)
    episode_ref: Optional[str] = Field(default=None, index=True)
    patient_ref: Optional[str] = Field(default=None, index=True)
    mode: str = Field(default="synthetic", index=True)
    status: str = Field(default="draft", index=True)
    current_stage: str = Field(default="created", index=True)
    step_count: int = 0
    passed_count: int = 0
    partial_count: int = 0
    blocked_count: int = 0
    scenario_count: int = 0
    summary: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    external_boundaries: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    created_by_subject: str = Field(index=True)
    created_by_name: str
    created_by_role: str = Field(index=True)
    started_at: datetime = Field(default_factory=utc_now, index=True)
    completed_at: Optional[datetime] = Field(default=None, index=True)
    version: int = 1
    evidence_event_ref: Optional[str] = Field(default=None, index=True)
    updated_at: datetime = Field(default_factory=utc_now, index=True)


class OperationalProofStepV30(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("step_ref", name="uq_operationalproofstepv30_ref"),
        UniqueConstraint("run_ref", "step_code", name="uq_operationalproofstepv30_run_code"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    step_ref: str = Field(index=True)
    run_ref: str = Field(index=True)
    sequence: int = Field(index=True)
    step_code: str = Field(index=True)
    title: str
    surface: str = Field(index=True)
    expected: str
    status: str = Field(default="pending", index=True)
    observed: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    entity_refs: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    owner_role: str = Field(default="ops_manager", index=True)
    failure_root_cause: Optional[str] = None
    corrective_action: Optional[str] = None
    started_at: datetime = Field(default_factory=utc_now, index=True)
    completed_at: Optional[datetime] = Field(default=None, index=True)
    evidence_event_ref: Optional[str] = Field(default=None, index=True)


class OperationalProofScenarioV30(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("scenario_ref", name="uq_operationalproofscenariov30_ref"),
        UniqueConstraint("run_ref", "scenario_code", name="uq_operationalproofscenariov30_run_code"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    scenario_ref: str = Field(index=True)
    run_ref: str = Field(index=True)
    scenario_code: str = Field(index=True)
    title: str
    status: str = Field(default="pending", index=True)
    expected_detection: str
    observed: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    failure_detected: bool = False
    accountable_owner_visible: bool = False
    next_action_visible: bool = False
    evidence_visible: bool = False
    urgent_access_preserved: bool = True
    started_at: datetime = Field(default_factory=utc_now, index=True)
    completed_at: Optional[datetime] = Field(default=None, index=True)
    evidence_event_ref: Optional[str] = Field(default=None, index=True)


class MobileAcceptanceV30(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("assessment_ref", name="uq_mobileacceptancev30_ref"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    assessment_ref: str = Field(index=True)
    run_ref: str = Field(index=True)
    device_label: str
    operating_system: str
    browser: str
    viewport_width: int
    viewport_height: int
    secure_context: bool
    online: bool
    touch_capable: bool
    microphone_available: bool
    checks: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    status: str = Field(index=True)
    manual_hardware_confirmation: bool = False
    limitations: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    assessed_by_subject: str = Field(index=True)
    assessed_at: datetime = Field(default_factory=utc_now, index=True)
    evidence_event_ref: Optional[str] = Field(default=None, index=True)
