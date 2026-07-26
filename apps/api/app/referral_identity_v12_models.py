from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import Column, JSON, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ReferralIdentityIntakeV12(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("intake_ref", name="uq_referralidentityintakev12_ref"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    intake_ref: str = Field(index=True)
    premises_ref: str = Field(index=True)
    patient_name: str = Field(index=True)
    species: str = Field(index=True)
    breed: Optional[str] = Field(default=None, index=True)
    sex: Optional[str] = Field(default=None, index=True)
    date_of_birth_text: Optional[str] = Field(default=None, index=True)
    microchip_number: Optional[str] = Field(default=None, index=True)
    owner_name: str = Field(index=True)
    owner_email: Optional[str] = Field(default=None, index=True)
    owner_phone: Optional[str] = Field(default=None, index=True)
    owner_address: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    decision_authority_claimed: bool = True
    financial_responsibility_claimed: bool = True
    referral_payload: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    status: str = Field(default="received", index=True)
    patient_ref: Optional[str] = Field(default=None, index=True)
    owner_ref: Optional[str] = Field(default=None, index=True)
    referral_ref: Optional[str] = Field(default=None, index=True)
    episode_ref: Optional[str] = Field(default=None, index=True)
    duplicate_count: int = 0
    resolved_by_subject: Optional[str] = Field(default=None, index=True)
    resolution_reason: Optional[str] = None
    version: int = 1
    created_by_subject: str = Field(index=True)
    created_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now, index=True)
    evidence_event_ref: Optional[str] = Field(default=None, index=True)


class IdentityMatchReviewV12(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("review_ref", name="uq_identitymatchreviewv12_ref"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    review_ref: str = Field(index=True)
    intake_ref: str = Field(index=True)
    candidate_patient_ref: str = Field(index=True)
    candidate_owner_refs: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    match_score: int = Field(index=True)
    reasons: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    status: str = Field(default="pending", index=True)
    decision: Optional[str] = Field(default=None, index=True)
    decided_by_subject: Optional[str] = Field(default=None, index=True)
    decided_at: Optional[datetime] = Field(default=None, index=True)
    version: int = 1
    created_at: datetime = Field(default_factory=utc_now, index=True)
    evidence_event_ref: Optional[str] = Field(default=None, index=True)


class ReferralDocumentV12(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("document_ref", name="uq_referraldocumentv12_ref"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    document_ref: str = Field(index=True)
    intake_ref: Optional[str] = Field(default=None, index=True)
    referral_ref: Optional[str] = Field(default=None, index=True)
    episode_ref: Optional[str] = Field(default=None, index=True)
    patient_ref: Optional[str] = Field(default=None, index=True)
    document_type: str = Field(default="referral_letter", index=True)
    filename: str
    mime_type: str = Field(default="application/octet-stream", index=True)
    storage_ref: str = Field(index=True)
    checksum_sha256: str = Field(index=True)
    source_system: str = Field(default="manual_intake", index=True)
    received_at: datetime = Field(default_factory=utc_now, index=True)
    status: str = Field(default="received", index=True)
    verified: bool = False
    version: int = 1
    created_by_subject: str = Field(index=True)
    evidence_event_ref: Optional[str] = Field(default=None, index=True)


class ReferralTriageV12(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("triage_ref", name="uq_referraltriagev12_ref"),
        UniqueConstraint("referral_ref", name="uq_referraltriagev12_referral"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    triage_ref: str = Field(index=True)
    referral_ref: str = Field(index=True)
    episode_ref: str = Field(index=True)
    patient_ref: str = Field(index=True)
    category: str = Field(index=True)
    score: int = Field(index=True)
    rationale: str
    red_flags: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    response_due_at: datetime = Field(index=True)
    clinical_review_due_at: datetime = Field(index=True)
    assigned_role: str = Field(default="clinician", index=True)
    assigned_subject: Optional[str] = Field(default=None, index=True)
    status: str = Field(default="pending", index=True)
    acknowledged_at: Optional[datetime] = Field(default=None, index=True)
    completed_at: Optional[datetime] = Field(default=None, index=True)
    version: int = 1
    created_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now, index=True)
    evidence_event_ref: Optional[str] = Field(default=None, index=True)


class AccessReviewV12(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("review_ref", name="uq_accessreviewv12_ref"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    review_ref: str = Field(index=True)
    subject_ref: str = Field(index=True)
    subject_name: str
    platform_role: str = Field(index=True)
    identity_group: str = Field(index=True)
    requested_capabilities: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    restricted_capabilities: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    status: str = Field(default="pending", index=True)
    decision: Optional[str] = Field(default=None, index=True)
    reason: str
    due_at: datetime = Field(index=True)
    reviewer_subject: Optional[str] = Field(default=None, index=True)
    reviewer_role: Optional[str] = Field(default=None, index=True)
    decided_at: Optional[datetime] = Field(default=None, index=True)
    version: int = 1
    created_by_subject: str = Field(index=True)
    created_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now, index=True)
    evidence_event_ref: Optional[str] = Field(default=None, index=True)
