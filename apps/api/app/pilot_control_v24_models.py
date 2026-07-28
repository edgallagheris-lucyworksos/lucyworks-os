from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import Column, JSON, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PilotAuthorityV24(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("authority_ref", name="uq_pilotauthorityv24_ref"),
        UniqueConstraint("run_ref", name="uq_pilotauthorityv24_run"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    authority_ref: str = Field(index=True)
    run_ref: str = Field(index=True)
    premises_ref: str = Field(index=True)
    service_line: str = Field(default="referral", index=True)
    requested_mode: str = Field(default="synthetic", index=True)
    status: str = Field(default="draft", index=True)
    scope: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    success_criteria: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    stop_criteria: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    rollback_plan: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    integration_scope: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    automation_mode: str = Field(default="disabled", index=True)
    accountable_owner_subject: str = Field(index=True)
    accountable_owner_name: str
    accountable_owner_role: str = Field(index=True)
    clinical_owner_subject: Optional[str] = Field(default=None, index=True)
    clinical_owner_name: Optional[str] = None
    clinical_owner_role: Optional[str] = Field(default=None, index=True)
    activated_at: Optional[datetime] = Field(default=None, index=True)
    stopped_at: Optional[datetime] = Field(default=None, index=True)
    rollback_at: Optional[datetime] = Field(default=None, index=True)
    completed_at: Optional[datetime] = Field(default=None, index=True)
    plan_version: int = 1
    version: int = 1
    evidence_event_ref: Optional[str] = Field(default=None, index=True)
    created_by_subject: str = Field(index=True)
    created_by_name: str
    created_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now, index=True)


class PilotApprovalV24(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("approval_ref", name="uq_pilotapprovalv24_ref"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    approval_ref: str = Field(index=True)
    authority_ref: str = Field(index=True)
    approval_type: str = Field(index=True)
    decision: str = Field(index=True)
    reason: str
    acknowledgement: Optional[str] = None
    authority_version: int = 1
    actor_subject: str = Field(index=True)
    actor_name: str
    actor_role: str = Field(index=True)
    actor_auth_source: str
    evidence_event_ref: Optional[str] = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=utc_now, index=True)


class PilotControlActionV24(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("action_ref", name="uq_pilotcontrolactionv24_ref"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    action_ref: str = Field(index=True)
    authority_ref: str = Field(index=True)
    action_type: str = Field(index=True)
    reason: str
    previous_status: Optional[str] = Field(default=None, index=True)
    result_status: Optional[str] = Field(default=None, index=True)
    previous_state: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    result_state: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    actor_subject: str = Field(index=True)
    actor_name: str
    actor_role: str = Field(index=True)
    actor_auth_source: str
    evidence_event_ref: Optional[str] = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=utc_now, index=True)


class PilotShadowComparisonV24(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("comparison_ref", name="uq_pilotshadowcomparisonv24_ref"),
        UniqueConstraint("authority_ref", "external_ref", name="uq_pilotshadowcomparisonv24_external"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    comparison_ref: str = Field(index=True)
    authority_ref: str = Field(index=True)
    external_ref: str = Field(index=True)
    canonical_episode_ref: str = Field(index=True)
    patient_ref: Optional[str] = Field(default=None, index=True)
    source_system: str = Field(default="external_shadow_source", index=True)
    external_snapshot: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    canonical_snapshot: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    mismatch_codes: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    severity: str = Field(default="green", index=True)
    status: str = Field(default="pending", index=True)
    reviewed_by_subject: Optional[str] = Field(default=None, index=True)
    reviewed_by_name: Optional[str] = None
    review_note: Optional[str] = None
    reviewed_at: Optional[datetime] = Field(default=None, index=True)
    version: int = 1
    created_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now, index=True)


class PilotUATScenarioV24(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("scenario_ref", name="uq_pilotuatscenariov24_ref"),
        UniqueConstraint("authority_ref", "scenario_code", name="uq_pilotuatscenariov24_code"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    scenario_ref: str = Field(index=True)
    authority_ref: str = Field(index=True)
    scenario_code: str = Field(index=True)
    title: str
    actor_role: str = Field(index=True)
    workflow: str
    expected_outcome: str
    critical: bool = True
    status: str = Field(default="not_run", index=True)
    evidence_summary: Optional[str] = None
    tested_by_subject: Optional[str] = Field(default=None, index=True)
    tested_by_name: Optional[str] = None
    tested_at: Optional[datetime] = Field(default=None, index=True)
    version: int = 1
    created_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now, index=True)
