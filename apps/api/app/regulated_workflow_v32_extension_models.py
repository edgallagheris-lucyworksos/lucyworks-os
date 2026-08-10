from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ChargeProvenanceV32(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("charge_ref", name="uq_chargeprovenancev32_ref"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    charge_ref: str = Field(index=True)
    episode_ref: str = Field(index=True)
    patient_ref: str = Field(index=True)
    estimate_ref: Optional[str] = Field(default=None, index=True)
    estimate_line_ref: Optional[str] = Field(default=None, index=True)
    service_price_ref: Optional[str] = Field(default=None, index=True)
    category: str = Field(index=True)
    description: str
    quantity: float = 1
    unit_pence: int
    gross_pence: int
    third_party_cost_pence: Optional[int] = None
    markup_pence: Optional[int] = None
    external_supplier: Optional[str] = None
    source_system: str = Field(default="lucyworks", index=True)
    external_reference: Optional[str] = Field(default=None, index=True)
    status: str = Field(default="recorded", index=True)
    actor_subject: str = Field(index=True)
    created_at: datetime = Field(default_factory=utc_now, index=True)
    evidence_event_ref: Optional[str] = Field(default=None, index=True)


class ComplaintV32(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("complaint_ref", name="uq_complaintv32_ref"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    complaint_ref: str = Field(index=True)
    premises_ref: str = Field(index=True)
    episode_ref: Optional[str] = Field(default=None, index=True)
    patient_ref: Optional[str] = Field(default=None, index=True)
    owner_ref: Optional[str] = Field(default=None, index=True)
    channel: str = Field(index=True)
    category: str = Field(index=True)
    severity: str = Field(default="standard", index=True)
    summary: str
    status: str = Field(default="open", index=True)
    assigned_role: str = Field(default="ops_manager", index=True)
    assigned_subject: Optional[str] = Field(default=None, index=True)
    due_at: Optional[datetime] = Field(default=None, index=True)
    acknowledged_at: Optional[datetime] = Field(default=None, index=True)
    resolved_at: Optional[datetime] = Field(default=None, index=True)
    resolution: Optional[str] = None
    created_by_subject: str = Field(index=True)
    version: int = 1
    created_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now, index=True)
    evidence_event_ref: Optional[str] = Field(default=None, index=True)


class PrescriptionChoiceV32(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("choice_ref", name="uq_prescriptionchoicev32_ref"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    choice_ref: str = Field(index=True)
    episode_ref: str = Field(index=True)
    patient_ref: str = Field(index=True)
    owner_ref: Optional[str] = Field(default=None, index=True)
    medication_name: str
    medication_ref: Optional[str] = Field(default=None, index=True)
    written_prescription_offered: bool
    prescription_fee_pence: Optional[int] = None
    client_choice: str = Field(index=True)
    information_delivery_ref: Optional[str] = Field(default=None, index=True)
    ongoing_medication_notice_ref: Optional[str] = Field(default=None, index=True)
    recorded_by_subject: str = Field(index=True)
    recorded_at: datetime = Field(default_factory=utc_now, index=True)
    evidence_event_ref: Optional[str] = Field(default=None, index=True)
