from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import Column, JSON, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ServicePriceV32(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("price_ref", name="uq_servicepricev32_ref"),
        UniqueConstraint("premises_ref", "service_code", "version", name="uq_servicepricev32_site_service_version"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    price_ref: str = Field(index=True)
    organisation_ref: str = Field(default="reference", index=True)
    premises_ref: str = Field(index=True)
    service_code: str = Field(index=True)
    service_name: str = Field(index=True)
    category: str = Field(index=True)
    description: str = ""
    lower_price_pence: int
    upper_price_pence: int
    vat_included: bool = True
    standard_duration_minutes: Optional[int] = None
    inclusions: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    exclusions: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    interpretation_included: Optional[bool] = None
    status: str = Field(default="draft", index=True)
    version: int = 1
    effective_from: datetime = Field(default_factory=utc_now, index=True)
    effective_to: Optional[datetime] = Field(default=None, index=True)
    created_by_subject: str = Field(index=True)
    approved_by_subject: Optional[str] = Field(default=None, index=True)
    approved_at: Optional[datetime] = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=utc_now, index=True)
    evidence_event_ref: Optional[str] = Field(default=None, index=True)


class EstimateGovernanceV32(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("governance_ref", name="uq_estimategovernancev32_ref"),
        UniqueConstraint("estimate_ref", name="uq_estimategovernancev32_estimate"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    governance_ref: str = Field(index=True)
    estimate_ref: str = Field(index=True)
    previous_estimate_ref: Optional[str] = Field(default=None, index=True)
    episode_ref: str = Field(index=True)
    patient_ref: str = Field(index=True)
    previous_upper_total_pence: Optional[int] = None
    current_upper_total_pence: int
    increase_pence: int = 0
    increase_percent: Optional[float] = None
    written_estimate_required: bool = False
    written_update_required: bool = False
    update_threshold_pence: Optional[int] = None
    trigger_reason: str = "none"
    written_delivery_ref: Optional[str] = Field(default=None, index=True)
    owner_acknowledgement_ref: Optional[str] = Field(default=None, index=True)
    status: str = Field(default="evaluated", index=True)
    evaluated_at: datetime = Field(default_factory=utc_now, index=True)
    evaluated_by_subject: str = Field(index=True)
    evidence_event_ref: Optional[str] = Field(default=None, index=True)


class AIProvenanceV32(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("provenance_ref", name="uq_aiprovenancev32_ref"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    provenance_ref: str = Field(index=True)
    episode_ref: Optional[str] = Field(default=None, index=True)
    patient_ref: Optional[str] = Field(default=None, index=True)
    source_entity_type: str = Field(index=True)
    source_entity_ref: str = Field(index=True)
    output_kind: str = Field(index=True)
    provider: str = Field(index=True)
    model_name: str = Field(index=True)
    model_version: Optional[str] = Field(default=None, index=True)
    generated_at: datetime = Field(default_factory=utc_now, index=True)
    generated_by_subject: str = Field(index=True)
    input_refs: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    client_data_used: bool = False
    data_use_purpose: str = "clinical_assistance"
    legal_basis: Optional[str] = None
    client_consent_ref: Optional[str] = Field(default=None, index=True)
    training_use_permitted: bool = False
    status: str = Field(default="draft", index=True)
    reviewer_subject: Optional[str] = Field(default=None, index=True)
    reviewer_name: Optional[str] = None
    reviewer_role: Optional[str] = Field(default=None, index=True)
    reviewed_at: Optional[datetime] = Field(default=None, index=True)
    edit_summary: Optional[str] = None
    final_entity_ref: Optional[str] = Field(default=None, index=True)
    version: int = 1
    evidence_event_ref: Optional[str] = Field(default=None, index=True)
