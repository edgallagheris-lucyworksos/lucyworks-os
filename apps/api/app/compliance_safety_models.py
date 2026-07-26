from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SafetyCaseV10(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    safety_case_ref: str = Field(index=True, sa_column_kwargs={"unique": True})
    title: str
    scope: str
    release_version: str = Field(index=True)
    methodology: str
    status: str = Field(default="baseline_prepared", index=True)
    safety_owner_role: str = Field(default="governance_lead", index=True)
    clinical_owner_role: str = Field(default="clinical_director", index=True)
    safety_statement: str
    limitations_json: str = "[]"
    generated_from_baseline: str = Field(index=True)
    approved_for_target: Optional[str] = Field(default=None, index=True)
    approved_by_subject: Optional[str] = Field(default=None, index=True)
    approved_by_name: Optional[str] = None
    approved_at: Optional[datetime] = Field(default=None, index=True)
    version: int = 1
    created_by_subject: str = Field(index=True)
    created_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now, index=True)


class SafetyHazardV10(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    hazard_ref: str = Field(index=True, sa_column_kwargs={"unique": True})
    safety_case_ref: str = Field(index=True)
    code: str = Field(index=True)
    category: str = Field(index=True)
    title: str
    hazardous_situation: str
    potential_harm: str
    severity: int
    likelihood: int
    initial_risk: int = Field(index=True)
    controls_json: str = "[]"
    verification_json: str = "[]"
    evidence_refs_json: str = "[]"
    residual_severity: int
    residual_likelihood: int
    residual_risk: int = Field(index=True)
    status: str = Field(default="controlled_by_design", index=True)
    owner_role: str = Field(index=True)
    source_ids_json: str = "[]"
    version: int = 1
    created_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now, index=True)


class SafetyReviewV10(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    review_ref: str = Field(index=True, sa_column_kwargs={"unique": True})
    safety_case_ref: str = Field(index=True)
    review_type: str = Field(index=True)
    target: str = Field(index=True)
    outcome: str = Field(index=True)
    findings_json: str = "[]"
    reason: str
    reviewer_subject: str = Field(index=True)
    reviewer_name: str
    reviewer_role: str = Field(index=True)
    created_at: datetime = Field(default_factory=utc_now, index=True)


class DeploymentProfileV10(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    profile_ref: str = Field(index=True, sa_column_kwargs={"unique": True})
    environment_name: str = Field(index=True)
    organisation_name: Optional[str] = Field(default=None, index=True)
    target: str = Field(default="synthetic", index=True)
    data_mode: str = Field(default="synthetic", index=True)
    identity_mode: str = Field(default="reference_groups", index=True)
    vendor_mode: str = Field(default="contract_stubs", index=True)
    real_identity_confirmed: bool = False
    identity_evidence_ref: Optional[str] = Field(default=None, index=True)
    real_data_governance_confirmed: bool = False
    data_governance_evidence_ref: Optional[str] = Field(default=None, index=True)
    real_vendor_connections_confirmed: bool = False
    vendor_evidence_ref: Optional[str] = Field(default=None, index=True)
    clinical_safety_officer_confirmed: bool = False
    clinical_safety_officer_evidence_ref: Optional[str] = Field(default=None, index=True)
    dpi_a_approved: bool = False
    dpia_evidence_ref: Optional[str] = Field(default=None, index=True)
    penetration_test_confirmed: bool = False
    penetration_test_evidence_ref: Optional[str] = Field(default=None, index=True)
    staff_uat_confirmed: bool = False
    staff_uat_evidence_ref: Optional[str] = Field(default=None, index=True)
    blockers_json: str = "[]"
    status: str = Field(default="synthetic_ready", index=True)
    version: int = 1
    created_by_subject: str = Field(index=True)
    created_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now, index=True)
