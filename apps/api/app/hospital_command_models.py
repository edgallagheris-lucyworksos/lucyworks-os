from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import Column, JSON, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ReferralIntakeV9(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("referral_ref", name="uq_referralintakev9_ref"),
        UniqueConstraint("episode_ref", name="uq_referralintakev9_episode"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    referral_ref: str = Field(index=True)
    episode_ref: str = Field(index=True)
    patient_ref: str = Field(index=True)
    premises_ref: str = Field(index=True)
    source_type: str = Field(default="referring_vet", index=True)
    source_organisation: Optional[str] = Field(default=None, index=True)
    source_contact_name: Optional[str] = None
    source_contact_email: Optional[str] = None
    source_contact_phone: Optional[str] = None
    requested_service: str = Field(index=True)
    presenting_problem: str
    clinical_summary: str = ""
    urgency: str = Field(default="routine", index=True)
    requested_timeframe: Optional[str] = None
    attachments: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    status: str = Field(default="received", index=True)
    acceptance_reason: Optional[str] = None
    received_at: datetime = Field(default_factory=utc_now, index=True)
    accepted_at: Optional[datetime] = Field(default=None, index=True)
    accepted_by_subject: Optional[str] = Field(default=None, index=True)
    version: int = 1
    created_by_subject: str = Field(index=True)
    updated_at: datetime = Field(default_factory=utc_now, index=True)
    evidence_event_ref: Optional[str] = Field(default=None, index=True)


class ConsentAuthorisationV9(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("consent_ref", name="uq_consentauthorisationv9_ref"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    consent_ref: str = Field(index=True)
    episode_ref: str = Field(index=True)
    patient_ref: str = Field(index=True)
    owner_ref: str = Field(index=True)
    authority_link_ref: str = Field(index=True)
    consent_type: str = Field(index=True)
    scope: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    maximum_authorised_pence: Optional[int] = None
    currency: str = Field(default="GBP", index=True)
    decision_maker_name: str
    captured_channel: str = Field(index=True)
    captured_by_subject: str = Field(index=True)
    status: str = Field(default="active", index=True)
    valid_from: datetime = Field(default_factory=utc_now, index=True)
    valid_until: Optional[datetime] = Field(default=None, index=True)
    withdrawn_at: Optional[datetime] = Field(default=None, index=True)
    withdrawal_reason: Optional[str] = None
    version: int = 1
    created_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now, index=True)
    evidence_event_ref: Optional[str] = Field(default=None, index=True)


class EpisodeHandoverV9(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("handover_ref", name="uq_episodehandoverv9_ref"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    handover_ref: str = Field(index=True)
    episode_ref: str = Field(index=True)
    patient_ref: Optional[str] = Field(default=None, index=True)
    phase: str = Field(index=True)
    from_role: str = Field(index=True)
    from_subject: str = Field(index=True)
    from_area_ref: Optional[str] = Field(default=None, index=True)
    to_role: str = Field(index=True)
    to_subject: Optional[str] = Field(default=None, index=True)
    to_area_ref: Optional[str] = Field(default=None, index=True)
    priority: str = Field(default="amber", index=True)
    situation: str
    background: str = ""
    assessment: str = ""
    recommendation: str = ""
    risks: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    pending_actions: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    status: str = Field(default="offered", index=True)
    acknowledged_by_subject: Optional[str] = Field(default=None, index=True)
    acknowledged_at: Optional[datetime] = Field(default=None, index=True)
    version: int = 1
    created_at: datetime = Field(default_factory=utc_now, index=True)
    evidence_event_ref: Optional[str] = Field(default=None, index=True)


class EpisodeCheckpointV9(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("checkpoint_ref", name="uq_episodecheckpointv9_ref"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    checkpoint_ref: str = Field(index=True)
    episode_ref: str = Field(index=True)
    checkpoint_code: str = Field(index=True)
    status: str = Field(default="passed", index=True)
    detail: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    verified_by_subject: str = Field(index=True)
    verified_by_role: str = Field(index=True)
    reason: str
    valid_until: Optional[datetime] = Field(default=None, index=True)
    supersedes_checkpoint_ref: Optional[str] = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=utc_now, index=True)
    evidence_event_ref: Optional[str] = Field(default=None, index=True)


class EpisodeTransitionV9(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("transition_ref", name="uq_episodetransitionv9_ref"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    transition_ref: str = Field(index=True)
    episode_ref: str = Field(index=True)
    patient_ref: Optional[str] = Field(default=None, index=True)
    from_phase: str = Field(index=True)
    to_phase: str = Field(index=True)
    command_ref: str = Field(index=True)
    status: str = Field(index=True)
    blockers: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    warnings: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    actor_subject: str = Field(index=True)
    actor_role: str = Field(index=True)
    reason: str
    created_at: datetime = Field(default_factory=utc_now, index=True)
    completed_at: Optional[datetime] = Field(default=None, index=True)
    evidence_event_ref: Optional[str] = Field(default=None, index=True)


class EpisodeClosureV9(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("closure_ref", name="uq_episodeclosurev9_ref"),
        UniqueConstraint("episode_ref", name="uq_episodeclosurev9_episode"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    closure_ref: str = Field(index=True)
    episode_ref: str = Field(index=True)
    patient_ref: str = Field(index=True)
    disposition: str = Field(index=True)
    discharge_document_ref: Optional[str] = Field(default=None, index=True)
    owner_communication_ref: Optional[str] = Field(default=None, index=True)
    referrer_communication_ref: Optional[str] = Field(default=None, index=True)
    final_estimate_ref: Optional[str] = Field(default=None, index=True)
    financial_status: str = Field(default="pending", index=True)
    outstanding_actions: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    retained_risks: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    status: str = Field(default="draft", index=True)
    prepared_by_subject: str = Field(index=True)
    approved_by_subject: Optional[str] = Field(default=None, index=True)
    approved_at: Optional[datetime] = Field(default=None, index=True)
    completed_at: Optional[datetime] = Field(default=None, index=True)
    version: int = 1
    created_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now, index=True)
    evidence_event_ref: Optional[str] = Field(default=None, index=True)
