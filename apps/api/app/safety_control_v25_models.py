from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import Column, JSON, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SafetyRecordV25(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("record_ref", name="uq_safetyrecordv25_ref"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    record_ref: str = Field(index=True)
    record_type: str = Field(index=True)
    domain: str = Field(index=True)
    confidentiality: str = Field(default="standard", index=True)
    reporter_visibility: str = Field(default="named", index=True)
    severity: str = Field(default="amber", index=True)
    status: str = Field(default="reported", index=True)
    title: str
    summary: str
    description: str = ""
    premises_ref: str = Field(default="default-premises", index=True)
    patient_ref: Optional[str] = Field(default=None, index=True)
    episode_ref: Optional[str] = Field(default=None, index=True)
    affected_staff_subject: Optional[str] = Field(default=None, index=True)
    affected_staff_name: Optional[str] = None
    source_module: str = Field(default="manual", index=True)
    source_record_ref: Optional[str] = Field(default=None, index=True)
    immediate_risk: bool = False
    safety_hold_requested: bool = False
    operational_impact: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    protective_summary: Optional[str] = None
    accountable_owner_subject: Optional[str] = Field(default=None, index=True)
    accountable_owner_name: Optional[str] = None
    accountable_owner_role: Optional[str] = Field(default=None, index=True)
    clinical_owner_subject: Optional[str] = Field(default=None, index=True)
    clinical_owner_name: Optional[str] = None
    clinical_owner_role: Optional[str] = Field(default=None, index=True)
    independent_owner_subject: Optional[str] = Field(default=None, index=True)
    independent_owner_name: Optional[str] = None
    independent_owner_role: Optional[str] = Field(default=None, index=True)
    conflict_subjects: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    root_cause: Optional[str] = None
    recurrence_controls: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    due_at: Optional[datetime] = Field(default=None, index=True)
    escalated_at: Optional[datetime] = Field(default=None, index=True)
    closed_at: Optional[datetime] = Field(default=None, index=True)
    version: int = 1
    evidence_event_ref: Optional[str] = Field(default=None, index=True)
    created_by_subject: str = Field(index=True)
    created_by_name: str
    created_by_role: str = Field(index=True)
    created_by_auth_source: str
    created_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now, index=True)


class SafetyActionV25(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("action_ref", name="uq_safetyactionv25_ref"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    action_ref: str = Field(index=True)
    record_ref: str = Field(index=True)
    action_type: str = Field(index=True)
    title: str
    description: str = ""
    owner_subject: str = Field(index=True)
    owner_name: str
    owner_role: str = Field(index=True)
    status: str = Field(default="open", index=True)
    due_at: Optional[datetime] = Field(default=None, index=True)
    completion_evidence: Optional[str] = None
    completed_at: Optional[datetime] = Field(default=None, index=True)
    requires_independent_verification: bool = True
    verification_status: str = Field(default="pending", index=True)
    verified_by_subject: Optional[str] = Field(default=None, index=True)
    verified_by_name: Optional[str] = None
    verified_by_role: Optional[str] = Field(default=None, index=True)
    verification_note: Optional[str] = None
    verified_at: Optional[datetime] = Field(default=None, index=True)
    work_item_id: Optional[int] = Field(default=None, foreign_key="workitem.id")
    version: int = 1
    evidence_event_ref: Optional[str] = Field(default=None, index=True)
    created_by_subject: str = Field(index=True)
    created_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now, index=True)


class SafetyDecisionV25(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("decision_ref", name="uq_safetydecisionv25_ref"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    decision_ref: str = Field(index=True)
    record_ref: str = Field(index=True)
    decision_type: str = Field(index=True)
    decision: str = Field(index=True)
    reason: str
    previous_state: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    result_state: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    actor_subject: str = Field(index=True)
    actor_name: str
    actor_role: str = Field(index=True)
    actor_auth_source: str
    evidence_event_ref: Optional[str] = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=utc_now, index=True)


class SafetyLinkV25(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("link_ref", name="uq_safetylinkv25_ref"),
        UniqueConstraint("record_ref", "entity_type", "entity_ref", "relationship", name="uq_safetylinkv25_entity"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    link_ref: str = Field(index=True)
    record_ref: str = Field(index=True)
    entity_type: str = Field(index=True)
    entity_ref: str = Field(index=True)
    relationship: str = Field(default="related", index=True)
    visibility: str = Field(default="standard", index=True)
    created_by_subject: str = Field(index=True)
    created_at: datetime = Field(default_factory=utc_now, index=True)


class SafetyEscalationV25(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("escalation_ref", name="uq_safetyescalationv25_ref"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    escalation_ref: str = Field(index=True)
    record_ref: str = Field(index=True)
    reason: str
    from_subject: Optional[str] = Field(default=None, index=True)
    from_role: Optional[str] = Field(default=None, index=True)
    to_subject: Optional[str] = Field(default=None, index=True)
    to_role: str = Field(index=True)
    status: str = Field(default="open", index=True)
    due_at: Optional[datetime] = Field(default=None, index=True)
    resolved_at: Optional[datetime] = Field(default=None, index=True)
    resolution_note: Optional[str] = None
    actor_subject: str = Field(index=True)
    actor_name: str
    actor_role: str = Field(index=True)
    evidence_event_ref: Optional[str] = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=utc_now, index=True)


class SafetyAccessEventV25(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("access_ref", name="uq_safetyaccesseventv25_ref"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    access_ref: str = Field(index=True)
    record_ref: str = Field(index=True)
    access_type: str = Field(default="view", index=True)
    reason: Optional[str] = None
    actor_subject: str = Field(index=True)
    actor_name: str
    actor_role: str = Field(index=True)
    actor_auth_source: str
    created_at: datetime = Field(default_factory=utc_now, index=True)
