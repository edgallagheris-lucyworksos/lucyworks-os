from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import Column, JSON, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class MedicationOrder(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("order_ref", name="uq_medicationorder_ref"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    order_ref: str = Field(index=True)
    episode_ref: str = Field(index=True)
    patient_ref: Optional[str] = Field(default=None, index=True)
    medication_ref: str = Field(index=True)
    medication_name: str
    dose: str
    route: str
    frequency: str
    indication: str
    starts_at: datetime = Field(index=True)
    ends_at: Optional[datetime] = Field(default=None, index=True)
    prescriber_subject: str = Field(index=True)
    prescriber_name: str
    status: str = Field(default="active", index=True)
    high_risk: bool = False
    controlled_drug: bool = False
    version: int = 1
    created_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now, index=True)


class MedicationAdministration(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("administration_ref", name="uq_medicationadministration_ref"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    administration_ref: str = Field(index=True)
    order_ref: str = Field(index=True)
    episode_ref: str = Field(index=True)
    scheduled_at: datetime = Field(index=True)
    administered_at: Optional[datetime] = Field(default=None, index=True)
    status: str = Field(default="due", index=True)
    dose_given: Optional[str] = None
    route_used: Optional[str] = None
    administered_by_subject: Optional[str] = Field(default=None, index=True)
    administered_by_name: Optional[str] = None
    witnessed_by_subject: Optional[str] = Field(default=None, index=True)
    omission_reason: Optional[str] = None
    adverse_reaction: Optional[str] = None
    version: int = 1
    evidence_event_ref: Optional[str] = Field(default=None, index=True)


class AnaesthesiaRecord(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("record_ref", name="uq_anaesthesiarecord_ref"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    record_ref: str = Field(index=True)
    episode_ref: str = Field(index=True)
    block_ref: Optional[str] = Field(default=None, index=True)
    responsible_clinician_subject: str = Field(index=True)
    responsible_clinician_name: str
    anaesthetist_subject: Optional[str] = Field(default=None, index=True)
    asa_status: Optional[str] = None
    airway_plan: Optional[str] = None
    analgesia_plan: Optional[str] = None
    induction_at: Optional[datetime] = Field(default=None, index=True)
    recovery_at: Optional[datetime] = Field(default=None, index=True)
    status: str = Field(default="planned", index=True)
    checklist: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    complications: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    version: int = 1
    evidence_event_ref: Optional[str] = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now, index=True)


class ClinicalObservation(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("observation_ref", name="uq_clinicalobservation_ref"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    observation_ref: str = Field(index=True)
    episode_ref: str = Field(index=True)
    area_ref: Optional[str] = Field(default=None, index=True)
    observation_type: str = Field(index=True)
    values: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    concern_level: str = Field(default="green", index=True)
    escalation_required: bool = False
    escalation_status: str = Field(default="not_required", index=True)
    recorded_by_subject: str = Field(index=True)
    recorded_by_name: str
    recorded_at: datetime = Field(default_factory=utc_now, index=True)
    evidence_event_ref: Optional[str] = Field(default=None, index=True)


class TreatmentTask(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("task_ref", name="uq_treatmenttask_ref"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    task_ref: str = Field(index=True)
    episode_ref: str = Field(index=True)
    task_type: str = Field(index=True)
    title: str
    instructions: str
    due_at: datetime = Field(index=True)
    assigned_role: str = Field(index=True)
    assigned_subject: Optional[str] = Field(default=None, index=True)
    status: str = Field(default="due", index=True)
    priority: str = Field(default="amber", index=True)
    requires_witness: bool = False
    completed_by_subject: Optional[str] = Field(default=None, index=True)
    completed_at: Optional[datetime] = Field(default=None, index=True)
    version: int = 1
    evidence_event_ref: Optional[str] = Field(default=None, index=True)


class ControlledDrugLedgerEntry(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("entry_ref", name="uq_controlleddrugentry_ref"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    entry_ref: str = Field(index=True)
    medication_ref: str = Field(index=True)
    batch_ref: Optional[str] = Field(default=None, index=True)
    episode_ref: Optional[str] = Field(default=None, index=True)
    movement_type: str = Field(index=True)
    quantity: float
    unit: str
    running_balance: float
    reason: str
    actor_subject: str = Field(index=True)
    actor_name: str
    witness_subject: Optional[str] = Field(default=None, index=True)
    witness_name: Optional[str] = None
    discrepancy: bool = False
    discrepancy_status: str = Field(default="none", index=True)
    created_at: datetime = Field(default_factory=utc_now, index=True)
    evidence_event_ref: Optional[str] = Field(default=None, index=True)


class InventoryItem(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("item_ref", name="uq_inventoryitem_ref"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    item_ref: str = Field(index=True)
    name: str
    item_type: str = Field(index=True)
    batch_ref: Optional[str] = Field(default=None, index=True)
    expires_at: Optional[datetime] = Field(default=None, index=True)
    quantity_on_hand: float = 0
    unit: str
    reorder_level: float = 0
    location_ref: Optional[str] = Field(default=None, index=True)
    controlled_drug: bool = False
    version: int = 1
    updated_at: datetime = Field(default_factory=utc_now, index=True)


class DiagnosticWorkItem(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("work_ref", name="uq_diagnosticwork_ref"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    work_ref: str = Field(index=True)
    episode_ref: str = Field(index=True)
    modality: str = Field(index=True)
    requested_test: str
    urgency: str = Field(default="routine", index=True)
    status: str = Field(default="requested", index=True)
    specimen_ref: Optional[str] = Field(default=None, index=True)
    accession_ref: Optional[str] = Field(default=None, index=True)
    requested_by_subject: str = Field(index=True)
    assigned_service: Optional[str] = Field(default=None, index=True)
    acquired_at: Optional[datetime] = Field(default=None, index=True)
    reported_at: Optional[datetime] = Field(default=None, index=True)
    report_summary: Optional[str] = None
    critical_result: bool = False
    version: int = 1
    evidence_event_ref: Optional[str] = Field(default=None, index=True)


class SampleChainEvent(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("event_ref", name="uq_samplechainevent_ref"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    event_ref: str = Field(index=True)
    specimen_ref: str = Field(index=True)
    episode_ref: str = Field(index=True)
    event_type: str = Field(index=True)
    location_ref: Optional[str] = Field(default=None, index=True)
    actor_subject: str = Field(index=True)
    actor_name: str
    occurred_at: datetime = Field(default_factory=utc_now, index=True)
    detail: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))


class DischargePlan(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("plan_ref", name="uq_dischargeplan_ref"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    plan_ref: str = Field(index=True)
    episode_ref: str = Field(index=True)
    status: str = Field(default="draft", index=True)
    medication_summary: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    care_instructions: str = ""
    follow_up: str = ""
    warning_signs: str = ""
    referring_vet_report_status: str = Field(default="not_started", index=True)
    owner_communication_status: str = Field(default="not_started", index=True)
    approved_by_subject: Optional[str] = Field(default=None, index=True)
    approved_by_name: Optional[str] = None
    approved_at: Optional[datetime] = Field(default=None, index=True)
    version: int = 1
    evidence_event_ref: Optional[str] = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now, index=True)
