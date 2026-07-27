from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import Column, JSON, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ProductImportBatchV18(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("batch_ref", name="uq_productimportbatchv18_ref"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    batch_ref: str = Field(index=True)
    source_name: str = Field(default="VMD Product Information Database", index=True)
    source_url: str
    source_sha256: str = Field(index=True)
    source_format: str = Field(default="xml", index=True)
    schema_fingerprint: str
    status: str = Field(default="completed", index=True)
    product_count: int = 0
    created_count: int = 0
    updated_count: int = 0
    unchanged_count: int = 0
    imported_by_subject: str = Field(index=True)
    imported_by_name: str
    imported_at: datetime = Field(default_factory=utc_now, index=True)
    evidence_event_ref: Optional[str] = Field(default=None, index=True)


class VeterinaryProductV18(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint(
            "source_name",
            "territory",
            "source_product_id",
            name="uq_veterinaryproductv18_source_territory_id",
        ),
        UniqueConstraint("product_ref", name="uq_veterinaryproductv18_ref"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    product_ref: str = Field(index=True)
    source_name: str = Field(default="VMD Product Information Database", index=True)
    source_product_id: str = Field(index=True)
    territory: str = Field(index=True)
    product_name: str = Field(index=True)
    marketing_authorisation_holder: Optional[str] = Field(default=None, index=True)
    distribution_category: Optional[str] = Field(default=None, index=True)
    authorisation_status: str = Field(default="current", index=True)
    pharmaceutical_form: Optional[str] = Field(default=None, index=True)
    active_substances: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    target_species: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    routes: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    strengths: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    concentration_mg_per_ml: Optional[float] = None
    contraindications: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    warnings: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    withdrawal_periods: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    spc_version: Optional[str] = Field(default=None, index=True)
    source_updated_at: Optional[datetime] = Field(default=None, index=True)
    source_url: Optional[str] = None
    source_hash: str = Field(index=True)
    imported_batch_ref: str = Field(index=True)
    version: int = 1
    created_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now, index=True)


class MedicationProtocolV18(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("protocol_ref", name="uq_medicationprotocolv18_ref"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    protocol_ref: str = Field(index=True)
    organisation_ref: str = Field(default="reference", index=True)
    product_ref: Optional[str] = Field(default=None, index=True)
    generic_name: str = Field(index=True)
    species: str = Field(index=True)
    indication: str = Field(index=True)
    route: str = Field(index=True)
    dose_basis: str = Field(default="mg_per_kg", index=True)
    recommended_mg_per_kg: float
    minimum_mg_per_kg: Optional[float] = None
    maximum_mg_per_kg: Optional[float] = None
    maximum_single_dose_mg: Optional[float] = None
    interval_hours: Optional[float] = None
    concentration_override_mg_per_ml: Optional[float] = None
    renal_adjustment: Optional[str] = None
    hepatic_adjustment: Optional[str] = None
    source_type: str = Field(index=True)
    source_reference: str
    source_version: str
    status: str = Field(default="draft", index=True)
    approved_by_subject: Optional[str] = Field(default=None, index=True)
    approved_by_name: Optional[str] = None
    approved_at: Optional[datetime] = Field(default=None, index=True)
    review_due_at: Optional[datetime] = Field(default=None, index=True)
    version: int = 1
    created_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now, index=True)
    evidence_event_ref: Optional[str] = Field(default=None, index=True)


class DoseCalculationV18(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("calculation_ref", name="uq_dosecalculationv18_ref"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    calculation_ref: str = Field(index=True)
    patient_ref: str = Field(index=True)
    episode_ref: str = Field(index=True)
    product_ref: str = Field(index=True)
    protocol_ref: str = Field(index=True)
    weight_ref: str = Field(index=True)
    weight_kg: float
    dose_mg_per_kg: float
    calculated_dose_mg: float
    concentration_mg_per_ml: Optional[float] = None
    calculated_volume_ml: Optional[float] = None
    rounded_volume_ml: Optional[float] = None
    rounding_increment_ml: Optional[float] = None
    route: str
    indication: str
    outcome: str = Field(index=True)
    warnings: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    blockers: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    source_snapshot: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    calculated_by_subject: str = Field(index=True)
    calculated_by_name: str
    created_at: datetime = Field(default_factory=utc_now, index=True)
    evidence_event_ref: Optional[str] = Field(default=None, index=True)


class MedicationProposalV18(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("proposal_ref", name="uq_medicationproposalv18_ref"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    proposal_ref: str = Field(index=True)
    calculation_ref: str = Field(index=True)
    safety_review_ref: Optional[str] = Field(default=None, index=True)
    patient_ref: str = Field(index=True)
    episode_ref: str = Field(index=True)
    product_ref: str = Field(index=True)
    protocol_ref: str = Field(index=True)
    medication_name: str
    dose_mg: float
    volume_ml: Optional[float] = None
    route: str
    frequency: str
    status: str = Field(default="calculated", index=True)
    created_by_subject: str = Field(index=True)
    created_by_name: str
    reviewed_by_subject: Optional[str] = Field(default=None, index=True)
    reviewed_by_name: Optional[str] = None
    reviewed_at: Optional[datetime] = Field(default=None, index=True)
    prescription_order_ref: Optional[str] = Field(default=None, index=True)
    rejection_reason: Optional[str] = None
    version: int = 1
    created_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now, index=True)
    evidence_event_ref: Optional[str] = Field(default=None, index=True)
