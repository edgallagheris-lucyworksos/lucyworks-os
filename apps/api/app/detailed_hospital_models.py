from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Optional

from sqlalchemy import Column, JSON, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class OwnerAccountV8(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("owner_ref", name="uq_owneraccountv8_ref"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    owner_ref: str = Field(index=True)
    display_name: str
    email: Optional[str] = Field(default=None, index=True)
    phone: Optional[str] = None
    address: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    communication_preferences: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    identity_verified: bool = False
    version: int = 1
    created_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now, index=True)
    evidence_event_ref: Optional[str] = Field(default=None, index=True)


class PatientClinicalRecordV8(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("patient_ref", name="uq_patientclinicalrecordv8_ref"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    patient_ref: str = Field(index=True)
    display_name: str
    species: str = Field(index=True)
    breed: Optional[str] = Field(default=None, index=True)
    sex: Optional[str] = Field(default=None, index=True)
    neuter_status: Optional[str] = None
    date_of_birth: Optional[date] = Field(default=None, index=True)
    microchip_number: Optional[str] = Field(default=None, index=True)
    deceased_at: Optional[datetime] = Field(default=None, index=True)
    status: str = Field(default="active", index=True)
    alerts: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    version: int = 1
    created_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now, index=True)
    evidence_event_ref: Optional[str] = Field(default=None, index=True)


class PatientOwnerLinkV8(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("link_ref", name="uq_patientownerlinkv8_ref"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    link_ref: str = Field(index=True)
    patient_ref: str = Field(index=True)
    owner_ref: str = Field(index=True)
    relationship: str = Field(default="registered_owner", index=True)
    decision_authority: bool = True
    financial_responsibility: bool = True
    active: bool = True
    starts_at: datetime = Field(default_factory=utc_now, index=True)
    ends_at: Optional[datetime] = Field(default=None, index=True)
    evidence_event_ref: Optional[str] = Field(default=None, index=True)


class PatientProblemV8(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("problem_ref", name="uq_patientproblemv8_ref"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    problem_ref: str = Field(index=True)
    patient_ref: str = Field(index=True)
    episode_ref: Optional[str] = Field(default=None, index=True)
    title: str
    description: str = ""
    status: str = Field(default="active", index=True)
    onset_at: Optional[datetime] = Field(default=None, index=True)
    resolved_at: Optional[datetime] = Field(default=None, index=True)
    recorded_by_subject: str = Field(index=True)
    version: int = 1
    created_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now, index=True)
    evidence_event_ref: Optional[str] = Field(default=None, index=True)


class PatientAllergyV8(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("allergy_ref", name="uq_patientallergyv8_ref"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    allergy_ref: str = Field(index=True)
    patient_ref: str = Field(index=True)
    substance_ref: Optional[str] = Field(default=None, index=True)
    substance_name: str = Field(index=True)
    reaction: str
    severity: str = Field(default="amber", index=True)
    status: str = Field(default="active", index=True)
    confirmed: bool = False
    recorded_by_subject: str = Field(index=True)
    version: int = 1
    created_at: datetime = Field(default_factory=utc_now, index=True)
    evidence_event_ref: Optional[str] = Field(default=None, index=True)


class PatientWeightV8(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("weight_ref", name="uq_patientweightv8_ref"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    weight_ref: str = Field(index=True)
    patient_ref: str = Field(index=True)
    episode_ref: Optional[str] = Field(default=None, index=True)
    weight_kg: float
    body_condition_score: Optional[str] = None
    measured_at: datetime = Field(default_factory=utc_now, index=True)
    measured_by_subject: str = Field(index=True)
    evidence_event_ref: Optional[str] = Field(default=None, index=True)


class ClinicalEncounterV8(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("encounter_ref", name="uq_clinicalencounterv8_ref"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    encounter_ref: str = Field(index=True)
    patient_ref: str = Field(index=True)
    episode_ref: str = Field(index=True)
    encounter_type: str = Field(index=True)
    service_ref: Optional[str] = Field(default=None, index=True)
    location_ref: Optional[str] = Field(default=None, index=True)
    responsible_clinician_subject: str = Field(index=True)
    status: str = Field(default="open", index=True)
    started_at: datetime = Field(default_factory=utc_now, index=True)
    ended_at: Optional[datetime] = Field(default=None, index=True)
    presenting_complaint: str = ""
    history: str = ""
    examination: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    assessment: str = ""
    plan: str = ""
    version: int = 1
    created_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now, index=True)
    evidence_event_ref: Optional[str] = Field(default=None, index=True)


class ClinicalNoteV8(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("note_ref", name="uq_clinicalnotev8_ref"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    note_ref: str = Field(index=True)
    patient_ref: str = Field(index=True)
    episode_ref: str = Field(index=True)
    encounter_ref: Optional[str] = Field(default=None, index=True)
    note_type: str = Field(index=True)
    title: str
    body: str
    status: str = Field(default="signed", index=True)
    author_subject: str = Field(index=True)
    author_name: str
    signed_at: datetime = Field(default_factory=utc_now, index=True)
    supersedes_note_ref: Optional[str] = Field(default=None, index=True)
    evidence_event_ref: Optional[str] = Field(default=None, index=True)


class FormularyMedicineV8(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("medicine_ref", name="uq_formularymedicinev8_ref"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    medicine_ref: str = Field(index=True)
    generic_name: str = Field(index=True)
    brand_names: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    controlled_schedule: Optional[str] = Field(default=None, index=True)
    high_risk: bool = False
    antimicrobial_class: Optional[str] = Field(default=None, index=True)
    routes: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    contraindications: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    interactions: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    status: str = Field(default="draft", index=True)
    version: int = 1
    approved_by_subject: Optional[str] = Field(default=None, index=True)
    approved_at: Optional[datetime] = Field(default=None, index=True)
    evidence_event_ref: Optional[str] = Field(default=None, index=True)


class FormularyDoseRuleV8(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("rule_ref", name="uq_formularydoserulev8_ref"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    rule_ref: str = Field(index=True)
    medicine_ref: str = Field(index=True)
    species: str = Field(index=True)
    indication: str = Field(index=True)
    route: str = Field(index=True)
    minimum_mg_per_kg: Optional[float] = None
    maximum_mg_per_kg: Optional[float] = None
    maximum_single_dose_mg: Optional[float] = None
    minimum_interval_hours: Optional[float] = None
    renal_adjustment: Optional[str] = None
    hepatic_adjustment: Optional[str] = None
    source_reference: str
    status: str = Field(default="draft", index=True)
    version: int = 1
    evidence_event_ref: Optional[str] = Field(default=None, index=True)


class MedicationSafetyReviewV8(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("review_ref", name="uq_medicationsafetyreviewv8_ref"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    review_ref: str = Field(index=True)
    patient_ref: str = Field(index=True)
    episode_ref: str = Field(index=True)
    medicine_ref: str = Field(index=True)
    proposed_dose_mg: float
    proposed_route: str
    proposed_interval_hours: Optional[float] = None
    weight_kg: float
    calculated_mg_per_kg: float
    outcome: str = Field(index=True)
    warnings: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    blocks_order: bool = False
    reviewed_by_subject: str = Field(index=True)
    created_at: datetime = Field(default_factory=utc_now, index=True)
    evidence_event_ref: Optional[str] = Field(default=None, index=True)


class AnaesthesiaChartV8(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("chart_ref", name="uq_anaesthesiachartv8_ref"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    chart_ref: str = Field(index=True)
    patient_ref: str = Field(index=True)
    episode_ref: str = Field(index=True)
    procedure_ref: Optional[str] = Field(default=None, index=True)
    responsible_clinician_subject: str = Field(index=True)
    anaesthetist_subject: Optional[str] = Field(default=None, index=True)
    asa_status: Optional[str] = Field(default=None, index=True)
    pre_anaesthetic_assessment: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    machine_check: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    airway_plan: str = ""
    analgesia_plan: str = ""
    ventilation_plan: str = ""
    status: str = Field(default="planned", index=True)
    induction_at: Optional[datetime] = Field(default=None, index=True)
    extubation_at: Optional[datetime] = Field(default=None, index=True)
    recovery_complete_at: Optional[datetime] = Field(default=None, index=True)
    recovery_score: Optional[str] = None
    version: int = 1
    created_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now, index=True)
    evidence_event_ref: Optional[str] = Field(default=None, index=True)


class AnaesthesiaObservationV8(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("observation_ref", name="uq_anaesthesiaobservationv8_ref"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    observation_ref: str = Field(index=True)
    chart_ref: str = Field(index=True)
    recorded_at: datetime = Field(default_factory=utc_now, index=True)
    heart_rate: Optional[float] = None
    respiratory_rate: Optional[float] = None
    systolic_bp: Optional[float] = None
    mean_bp: Optional[float] = None
    diastolic_bp: Optional[float] = None
    spo2: Optional[float] = None
    etco2: Optional[float] = None
    temperature_c: Optional[float] = None
    anaesthetic_agent_percent: Optional[float] = None
    oxygen_flow_l_min: Optional[float] = None
    ventilator_settings: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    concern_level: str = Field(default="green", index=True)
    recorded_by_subject: str = Field(index=True)
    evidence_event_ref: Optional[str] = Field(default=None, index=True)


class AnaesthesiaDrugEventV8(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("drug_event_ref", name="uq_anaesthesiadrugv8_ref"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    drug_event_ref: str = Field(index=True)
    chart_ref: str = Field(index=True)
    medicine_ref: str = Field(index=True)
    medicine_name: str
    dose: str
    route: str
    event_type: str = Field(index=True)
    occurred_at: datetime = Field(default_factory=utc_now, index=True)
    actor_subject: str = Field(index=True)
    witness_subject: Optional[str] = Field(default=None, index=True)
    evidence_event_ref: Optional[str] = Field(default=None, index=True)


class FluidPlanV8(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("plan_ref", name="uq_fluidplanv8_ref"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    plan_ref: str = Field(index=True)
    patient_ref: str = Field(index=True)
    episode_ref: str = Field(index=True)
    fluid_type: str
    route: str = Field(index=True)
    rate_ml_per_hour: float
    target_total_ml: Optional[float] = None
    starts_at: datetime = Field(default_factory=utc_now, index=True)
    ends_at: Optional[datetime] = Field(default=None, index=True)
    indication: str
    prescriber_subject: str = Field(index=True)
    status: str = Field(default="active", index=True)
    version: int = 1
    evidence_event_ref: Optional[str] = Field(default=None, index=True)


class FluidBalanceEntryV8(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("entry_ref", name="uq_fluidbalanceentryv8_ref"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    entry_ref: str = Field(index=True)
    patient_ref: str = Field(index=True)
    episode_ref: str = Field(index=True)
    plan_ref: Optional[str] = Field(default=None, index=True)
    entry_type: str = Field(index=True)
    volume_ml: float
    route_or_source: str
    occurred_at: datetime = Field(default_factory=utc_now, index=True)
    actor_subject: str = Field(index=True)
    evidence_event_ref: Optional[str] = Field(default=None, index=True)


class InpatientCarePlanV8(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("care_plan_ref", name="uq_inpatientcareplanv8_ref"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    care_plan_ref: str = Field(index=True)
    patient_ref: str = Field(index=True)
    episode_ref: str = Field(index=True)
    area_ref: str = Field(index=True)
    acuity: str = Field(default="standard", index=True)
    goals: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    interventions: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    observation_schedule: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    nutrition_plan: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    mobility_plan: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    status: str = Field(default="active", index=True)
    responsible_nurse_subject: Optional[str] = Field(default=None, index=True)
    version: int = 1
    created_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now, index=True)
    evidence_event_ref: Optional[str] = Field(default=None, index=True)


class InpatientChartEntryV8(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("entry_ref", name="uq_inpatientchartentryv8_ref"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    entry_ref: str = Field(index=True)
    care_plan_ref: str = Field(index=True)
    patient_ref: str = Field(index=True)
    episode_ref: str = Field(index=True)
    entry_type: str = Field(index=True)
    values: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    concern_level: str = Field(default="green", index=True)
    note: str = ""
    recorded_at: datetime = Field(default_factory=utc_now, index=True)
    recorded_by_subject: str = Field(index=True)
    evidence_event_ref: Optional[str] = Field(default=None, index=True)


class ProcedureRecordV8(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("procedure_ref", name="uq_procedurerecordv8_ref"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    procedure_ref: str = Field(index=True)
    patient_ref: str = Field(index=True)
    episode_ref: str = Field(index=True)
    block_ref: Optional[str] = Field(default=None, index=True)
    procedure_name: str
    lead_clinician_subject: str = Field(index=True)
    assistants: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    preoperative_diagnosis: str = ""
    postoperative_diagnosis: str = ""
    findings: str = ""
    technique: str = ""
    complications: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    specimens: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    status: str = Field(default="planned", index=True)
    started_at: Optional[datetime] = Field(default=None, index=True)
    completed_at: Optional[datetime] = Field(default=None, index=True)
    version: int = 1
    evidence_event_ref: Optional[str] = Field(default=None, index=True)


class ImplantTraceV8(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("implant_ref", name="uq_implanttracev8_ref"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    implant_ref: str = Field(index=True)
    procedure_ref: str = Field(index=True)
    patient_ref: str = Field(index=True)
    product_name: str
    manufacturer: Optional[str] = Field(default=None, index=True)
    catalogue_number: Optional[str] = Field(default=None, index=True)
    lot_number: Optional[str] = Field(default=None, index=True)
    serial_number: Optional[str] = Field(default=None, index=True)
    expiry_date: Optional[date] = Field(default=None, index=True)
    implanted_at: datetime = Field(default_factory=utc_now, index=True)
    explanted_at: Optional[datetime] = Field(default=None, index=True)
    actor_subject: str = Field(index=True)
    evidence_event_ref: Optional[str] = Field(default=None, index=True)


class EstimateV8(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("estimate_ref", name="uq_estimatev8_ref"), UniqueConstraint("episode_ref", "version", name="uq_estimatev8_episode_version"))
    id: Optional[int] = Field(default=None, primary_key=True)
    estimate_ref: str = Field(index=True)
    patient_ref: str = Field(index=True)
    episode_ref: str = Field(index=True)
    version: int = 1
    status: str = Field(default="draft", index=True)
    lower_total_pence: int = 0
    upper_total_pence: int = 0
    authorised_limit_pence: Optional[int] = None
    currency: str = Field(default="GBP", index=True)
    reason_for_change: Optional[str] = None
    owner_authorisation_ref: Optional[str] = Field(default=None, index=True)
    created_by_subject: str = Field(index=True)
    approved_by_subject: Optional[str] = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=utc_now, index=True)
    approved_at: Optional[datetime] = Field(default=None, index=True)
    evidence_event_ref: Optional[str] = Field(default=None, index=True)


class EstimateLineV8(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("line_ref", name="uq_estimatelinev8_ref"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    line_ref: str = Field(index=True)
    estimate_ref: str = Field(index=True)
    category: str = Field(index=True)
    description: str
    quantity: float = 1
    lower_unit_pence: int
    upper_unit_pence: int
    tax_rate_percent: float = 20
    optional: bool = False
    source_catalogue_ref: Optional[str] = Field(default=None, index=True)


class InsuranceCaseV8(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("insurance_ref", name="uq_insurancecasev8_ref"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    insurance_ref: str = Field(index=True)
    patient_ref: str = Field(index=True)
    episode_ref: str = Field(index=True)
    owner_ref: str = Field(index=True)
    insurer_name: str = Field(index=True)
    policy_number_masked: str
    claim_reference: Optional[str] = Field(default=None, index=True)
    cover_limit_pence: Optional[int] = None
    excess_pence: Optional[int] = None
    preauthorised_pence: Optional[int] = None
    status: str = Field(default="details_received", index=True)
    direct_claim_requested: bool = False
    shortfall_pence: Optional[int] = None
    version: int = 1
    updated_at: datetime = Field(default_factory=utc_now, index=True)
    evidence_event_ref: Optional[str] = Field(default=None, index=True)


class FinancialTransactionV8(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("transaction_ref", name="uq_financialtransactionv8_ref"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    transaction_ref: str = Field(index=True)
    patient_ref: str = Field(index=True)
    episode_ref: str = Field(index=True)
    owner_ref: Optional[str] = Field(default=None, index=True)
    transaction_type: str = Field(index=True)
    amount_pence: int
    currency: str = Field(default="GBP", index=True)
    payment_method: Optional[str] = Field(default=None, index=True)
    external_reference: Optional[str] = Field(default=None, index=True)
    status: str = Field(default="recorded", index=True)
    occurred_at: datetime = Field(default_factory=utc_now, index=True)
    actor_subject: str = Field(index=True)
    evidence_event_ref: Optional[str] = Field(default=None, index=True)


class CommunicationEventV8(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("communication_ref", name="uq_communicationeventv8_ref"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    communication_ref: str = Field(index=True)
    patient_ref: str = Field(index=True)
    episode_ref: str = Field(index=True)
    owner_ref: Optional[str] = Field(default=None, index=True)
    audience: str = Field(index=True)
    channel: str = Field(index=True)
    direction: str = Field(index=True)
    subject: str
    summary: str
    outcome: Optional[str] = None
    consent_or_authorisation: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    attachments: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    occurred_at: datetime = Field(default_factory=utc_now, index=True)
    actor_subject: str = Field(index=True)
    evidence_event_ref: Optional[str] = Field(default=None, index=True)


class ClinicalDocumentV8(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("document_ref", name="uq_clinicaldocumentv8_ref"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    document_ref: str = Field(index=True)
    patient_ref: str = Field(index=True)
    episode_ref: str = Field(index=True)
    document_type: str = Field(index=True)
    title: str
    content: str
    status: str = Field(default="draft", index=True)
    version: int = 1
    generated_from: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    author_subject: str = Field(index=True)
    approved_by_subject: Optional[str] = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=utc_now, index=True)
    approved_at: Optional[datetime] = Field(default=None, index=True)
    sent_at: Optional[datetime] = Field(default=None, index=True)
    evidence_event_ref: Optional[str] = Field(default=None, index=True)
