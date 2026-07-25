from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field as PydanticField
from sqlmodel import Session, select

from app.auth import AuthContext, CLINICAL_ROLES, PRESCRIBER_ROLES, SENIOR_ROLES, require_authenticated, require_roles
from app.clinical_execution_models import MedicationOrder
from app.database import get_session
from app.detailed_hospital_models import (
    AnaesthesiaChartV8,
    AnaesthesiaDrugEventV8,
    AnaesthesiaObservationV8,
    ClinicalDocumentV8,
    ClinicalEncounterV8,
    ClinicalNoteV8,
    CommunicationEventV8,
    EstimateLineV8,
    EstimateV8,
    FinancialTransactionV8,
    FluidBalanceEntryV8,
    FluidPlanV8,
    FormularyDoseRuleV8,
    FormularyMedicineV8,
    ImplantTraceV8,
    InpatientCarePlanV8,
    InpatientChartEntryV8,
    InsuranceCaseV8,
    MedicationSafetyReviewV8,
    OwnerAccountV8,
    PatientAllergyV8,
    PatientClinicalRecordV8,
    PatientOwnerLinkV8,
    PatientProblemV8,
    PatientWeightV8,
    ProcedureRecordV8,
)
from app.evidence_service import create_evidence_event
from app.hospital_ops_models import CanonicalEpisodeState
from app.v7_event_service import publish_event

router = APIRouter(prefix="/api/v8", tags=["detailed-hospital-record-v8"])
FINANCIAL_ROLES = {"admin", "ops_manager", "hospital_director", "governance_lead"}
DOCUMENT_APPROVER_ROLES = set(SENIOR_ROLES) | {"clinician"}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_ref(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def row_dict(row: Any) -> dict[str, Any]:
    return row.model_dump(mode="json")


def require_episode(session: Session, episode_ref: str) -> CanonicalEpisodeState:
    row = session.exec(select(CanonicalEpisodeState).where(CanonicalEpisodeState.episode_ref == episode_ref)).first()
    if not row:
        raise HTTPException(status_code=404, detail="canonical episode not found")
    return row


def require_patient(session: Session, patient_ref: str) -> PatientClinicalRecordV8:
    row = session.exec(select(PatientClinicalRecordV8).where(PatientClinicalRecordV8.patient_ref == patient_ref)).first()
    if not row:
        raise HTTPException(status_code=404, detail="patient record not found")
    return row


def require_expected(current: int, expected: int | None, entity: str) -> None:
    if expected is not None and current != expected:
        raise HTTPException(status_code=409, detail={"message": f"stale {entity}", "currentVersion": current})


def record_evidence(
    session: Session,
    *,
    entity_type: str,
    entity_ref: str,
    action: str,
    episode_ref: str | None,
    patient_ref: str | None,
    previous: Any,
    current: Any,
    reason: str,
    risk: str = "amber",
    domain: str = "clinical_record",
) -> str:
    evidence, _ = create_evidence_event(
        session,
        event_type=f"v8_{entity_type}_{action}",
        action=action,
        patient_case_id=patient_ref,
        referral_episode_id=episode_ref,
        previous_state=previous,
        new_state=current,
        reason=reason,
        compliance_domain=domain,
        risk_level=risk,
        source_module="detailed-hospital-record-v8",
        source_record_ref=entity_ref,
        correlation_id=episode_ref or patient_ref,
        entity_type=entity_type,
        entity_id=entity_ref,
        idempotency_key=f"v8:{entity_type}:{entity_ref}:{action}:{current.get('version', current.get('status', 'event')) if isinstance(current, dict) else 'event'}",
    )
    publish_event(
        session,
        event_type=f"v8_{entity_type}_{action}",
        aggregate_type=entity_type,
        aggregate_ref=entity_ref,
        payload=current if isinstance(current, dict) else {"value": current},
        severity="error" if risk == "red" else "warning" if risk == "amber" else "info",
        correlation_id=episode_ref or patient_ref,
        idempotency_key=f"v8-event:{evidence.event_ref}",
    )
    return evidence.event_ref


class PatientUpsert(BaseModel):
    display_name: str
    species: str
    breed: str | None = None
    sex: str | None = None
    neuter_status: str | None = None
    date_of_birth: date | None = None
    microchip_number: str | None = None
    alerts: list[dict[str, Any]] = PydanticField(default_factory=list)
    expected_version: int | None = None
    reason: str


class OwnerUpsert(BaseModel):
    display_name: str
    email: str | None = None
    phone: str | None = None
    address: dict[str, Any] = PydanticField(default_factory=dict)
    communication_preferences: dict[str, Any] = PydanticField(default_factory=dict)
    identity_verified: bool = False
    expected_version: int | None = None
    reason: str


class OwnerLinkCreate(BaseModel):
    owner_ref: str
    relationship: str = "registered_owner"
    decision_authority: bool = True
    financial_responsibility: bool = True
    reason: str


class ProblemCreate(BaseModel):
    episode_ref: str | None = None
    title: str
    description: str = ""
    status: str = "active"
    onset_at: datetime | None = None
    reason: str


class AllergyCreate(BaseModel):
    substance_ref: str | None = None
    substance_name: str
    reaction: str
    severity: str = "amber"
    confirmed: bool = False
    reason: str


class WeightCreate(BaseModel):
    episode_ref: str | None = None
    weight_kg: float
    body_condition_score: str | None = None
    measured_at: datetime | None = None
    reason: str = "Clinical weight measurement"


class EncounterCreate(BaseModel):
    patient_ref: str
    encounter_type: str
    service_ref: str | None = None
    location_ref: str | None = None
    presenting_complaint: str = ""
    history: str = ""
    examination: dict[str, Any] = PydanticField(default_factory=dict)
    assessment: str = ""
    plan: str = ""
    reason: str = "Clinical encounter created"


class NoteCreate(BaseModel):
    patient_ref: str
    encounter_ref: str | None = None
    note_type: str
    title: str
    body: str
    supersedes_note_ref: str | None = None
    reason: str = "Clinical note signed"


class MedicineUpsert(BaseModel):
    generic_name: str
    brand_names: list[str] = PydanticField(default_factory=list)
    controlled_schedule: str | None = None
    high_risk: bool = False
    antimicrobial_class: str | None = None
    routes: list[str] = PydanticField(default_factory=list)
    contraindications: list[dict[str, Any]] = PydanticField(default_factory=list)
    interactions: list[dict[str, Any]] = PydanticField(default_factory=list)
    status: str = "draft"
    expected_version: int | None = None
    reason: str


class DoseRuleUpsert(BaseModel):
    medicine_ref: str
    species: str
    indication: str
    route: str
    minimum_mg_per_kg: float | None = None
    maximum_mg_per_kg: float | None = None
    maximum_single_dose_mg: float | None = None
    minimum_interval_hours: float | None = None
    renal_adjustment: str | None = None
    hepatic_adjustment: str | None = None
    source_reference: str
    status: str = "draft"
    expected_version: int | None = None
    reason: str


class MedicationSafetyRequest(BaseModel):
    patient_ref: str
    medicine_ref: str
    indication: str
    route: str
    dose_mg: float
    interval_hours: float | None = None
    reason: str = "Medication safety review"


class AnaesthesiaChartCreate(BaseModel):
    patient_ref: str
    procedure_ref: str | None = None
    anaesthetist_subject: str | None = None
    asa_status: str | None = None
    pre_anaesthetic_assessment: dict[str, Any] = PydanticField(default_factory=dict)
    machine_check: dict[str, Any] = PydanticField(default_factory=dict)
    airway_plan: str = ""
    analgesia_plan: str = ""
    ventilation_plan: str = ""
    reason: str = "Anaesthesia chart created"


class AnaesthesiaObservationCreate(BaseModel):
    heart_rate: float | None = None
    respiratory_rate: float | None = None
    systolic_bp: float | None = None
    mean_bp: float | None = None
    diastolic_bp: float | None = None
    spo2: float | None = None
    etco2: float | None = None
    temperature_c: float | None = None
    anaesthetic_agent_percent: float | None = None
    oxygen_flow_l_min: float | None = None
    ventilator_settings: dict[str, Any] = PydanticField(default_factory=dict)
    recorded_at: datetime | None = None
    reason: str = "Anaesthesia observation recorded"


class AnaesthesiaDrugCreate(BaseModel):
    medicine_ref: str
    medicine_name: str
    dose: str
    route: str
    event_type: str
    witness_subject: str | None = None
    occurred_at: datetime | None = None
    reason: str = "Anaesthesia drug event recorded"


class FluidPlanCreate(BaseModel):
    patient_ref: str
    fluid_type: str
    route: str = "IV"
    rate_ml_per_hour: float
    target_total_ml: float | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    indication: str
    reason: str = "Fluid plan prescribed"


class FluidEntryCreate(BaseModel):
    patient_ref: str
    plan_ref: str | None = None
    entry_type: str
    volume_ml: float
    route_or_source: str
    occurred_at: datetime | None = None
    reason: str = "Fluid balance entry recorded"


class CarePlanCreate(BaseModel):
    patient_ref: str
    area_ref: str
    acuity: str = "standard"
    goals: list[dict[str, Any]] = PydanticField(default_factory=list)
    interventions: list[dict[str, Any]] = PydanticField(default_factory=list)
    observation_schedule: dict[str, Any] = PydanticField(default_factory=dict)
    nutrition_plan: dict[str, Any] = PydanticField(default_factory=dict)
    mobility_plan: dict[str, Any] = PydanticField(default_factory=dict)
    responsible_nurse_subject: str | None = None
    reason: str = "Inpatient care plan created"


class ChartEntryCreate(BaseModel):
    entry_type: str
    values: dict[str, Any] = PydanticField(default_factory=dict)
    concern_level: str = "green"
    note: str = ""
    recorded_at: datetime | None = None
    reason: str = "Inpatient chart entry recorded"


class ProcedureCreate(BaseModel):
    patient_ref: str
    block_ref: str | None = None
    procedure_name: str
    assistants: list[dict[str, Any]] = PydanticField(default_factory=list)
    preoperative_diagnosis: str = ""
    postoperative_diagnosis: str = ""
    findings: str = ""
    technique: str = ""
    complications: list[dict[str, Any]] = PydanticField(default_factory=list)
    specimens: list[dict[str, Any]] = PydanticField(default_factory=list)
    status: str = "planned"
    reason: str = "Procedure record created"


class ImplantCreate(BaseModel):
    patient_ref: str
    product_name: str
    manufacturer: str | None = None
    catalogue_number: str | None = None
    lot_number: str | None = None
    serial_number: str | None = None
    expiry_date: date | None = None
    reason: str = "Implant trace recorded"


class EstimateLineInput(BaseModel):
    category: str
    description: str
    quantity: float = 1
    lower_unit_pence: int
    upper_unit_pence: int
    tax_rate_percent: float = 20
    optional: bool = False
    source_catalogue_ref: str | None = None


class EstimateCreate(BaseModel):
    patient_ref: str
    lines: list[EstimateLineInput]
    status: str = "draft"
    authorised_limit_pence: int | None = None
    owner_authorisation_ref: str | None = None
    reason_for_change: str | None = None
    reason: str = "Estimate version created"


class InsuranceCreate(BaseModel):
    patient_ref: str
    owner_ref: str
    insurer_name: str
    policy_number_masked: str
    claim_reference: str | None = None
    cover_limit_pence: int | None = None
    excess_pence: int | None = None
    preauthorised_pence: int | None = None
    direct_claim_requested: bool = False
    status: str = "details_received"
    reason: str = "Insurance case created"


class TransactionCreate(BaseModel):
    patient_ref: str
    owner_ref: str | None = None
    transaction_type: str
    amount_pence: int
    payment_method: str | None = None
    external_reference: str | None = None
    status: str = "recorded"
    reason: str = "Financial transaction recorded"


class CommunicationCreate(BaseModel):
    patient_ref: str
    owner_ref: str | None = None
    audience: str
    channel: str
    direction: str
    subject: str
    summary: str
    outcome: str | None = None
    consent_or_authorisation: dict[str, Any] = PydanticField(default_factory=dict)
    attachments: list[dict[str, Any]] = PydanticField(default_factory=list)
    occurred_at: datetime | None = None
    reason: str = "Communication recorded"


class DocumentGenerate(BaseModel):
    patient_ref: str
    document_type: str
    title: str | None = None
    additional_text: str = ""
    reason: str = "Clinical document generated"


@router.put("/patients/{patient_ref}")
def upsert_patient(patient_ref: str, payload: PatientUpsert, session: Session = Depends(get_session), auth: AuthContext = Depends(require_roles(*CLINICAL_ROLES, *SENIOR_ROLES))) -> dict[str, Any]:
    row = session.exec(select(PatientClinicalRecordV8).where(PatientClinicalRecordV8.patient_ref == patient_ref)).first()
    previous = row_dict(row) if row else None
    if row:
        require_expected(row.version, payload.expected_version, "patient record")
        row.version += 1
    else:
        row = PatientClinicalRecordV8(patient_ref=patient_ref, display_name=payload.display_name, species=payload.species)
    for field in ("display_name", "species", "breed", "sex", "neuter_status", "date_of_birth", "microchip_number", "alerts"):
        setattr(row, field, getattr(payload, field))
    row.updated_at = utc_now()
    session.add(row)
    current = row_dict(row)
    row.evidence_event_ref = record_evidence(session, entity_type="patient", entity_ref=patient_ref, action="upsert", episode_ref=None, patient_ref=patient_ref, previous=previous, current=current, reason=payload.reason, risk="green")
    session.add(row); session.commit(); session.refresh(row)
    return {"patient": row_dict(row)}


@router.put("/owners/{owner_ref}")
def upsert_owner(owner_ref: str, payload: OwnerUpsert, session: Session = Depends(get_session), auth: AuthContext = Depends(require_authenticated)) -> dict[str, Any]:
    row = session.exec(select(OwnerAccountV8).where(OwnerAccountV8.owner_ref == owner_ref)).first()
    previous = row_dict(row) if row else None
    if row:
        require_expected(row.version, payload.expected_version, "owner account")
        row.version += 1
    else:
        row = OwnerAccountV8(owner_ref=owner_ref, display_name=payload.display_name)
    for field in ("display_name", "email", "phone", "address", "communication_preferences", "identity_verified"):
        setattr(row, field, getattr(payload, field))
    row.updated_at = utc_now(); session.add(row)
    current = row_dict(row)
    row.evidence_event_ref = record_evidence(session, entity_type="owner", entity_ref=owner_ref, action="upsert", episode_ref=None, patient_ref=None, previous=previous, current=current, reason=payload.reason, domain="client_identity", risk="green")
    session.add(row); session.commit(); session.refresh(row)
    return {"owner": row_dict(row)}


@router.post("/patients/{patient_ref}/owners")
def link_owner(patient_ref: str, payload: OwnerLinkCreate, session: Session = Depends(get_session), auth: AuthContext = Depends(require_authenticated)) -> dict[str, Any]:
    require_patient(session, patient_ref)
    owner = session.exec(select(OwnerAccountV8).where(OwnerAccountV8.owner_ref == payload.owner_ref)).first()
    if not owner:
        raise HTTPException(status_code=404, detail="owner account not found")
    existing = session.exec(select(PatientOwnerLinkV8).where(PatientOwnerLinkV8.patient_ref == patient_ref, PatientOwnerLinkV8.owner_ref == payload.owner_ref, PatientOwnerLinkV8.active == True)).first()  # noqa: E712
    if existing:
        return {"link": row_dict(existing), "created": False}
    row = PatientOwnerLinkV8(link_ref=new_ref("owner-link"), patient_ref=patient_ref, owner_ref=payload.owner_ref, relationship=payload.relationship, decision_authority=payload.decision_authority, financial_responsibility=payload.financial_responsibility)
    session.add(row)
    row.evidence_event_ref = record_evidence(session, entity_type="patient_owner_link", entity_ref=row.link_ref, action="create", episode_ref=None, patient_ref=patient_ref, previous=None, current=row_dict(row), reason=payload.reason, domain="client_identity", risk="green")
    session.add(row); session.commit(); session.refresh(row)
    return {"link": row_dict(row), "created": True}


@router.post("/patients/{patient_ref}/problems")
def add_problem(patient_ref: str, payload: ProblemCreate, session: Session = Depends(get_session), auth: AuthContext = Depends(require_roles(*CLINICAL_ROLES))) -> dict[str, Any]:
    require_patient(session, patient_ref)
    row = PatientProblemV8(problem_ref=new_ref("problem"), patient_ref=patient_ref, episode_ref=payload.episode_ref, title=payload.title, description=payload.description, status=payload.status, onset_at=payload.onset_at, recorded_by_subject=auth.subject)
    session.add(row)
    row.evidence_event_ref = record_evidence(session, entity_type="problem", entity_ref=row.problem_ref, action="create", episode_ref=payload.episode_ref, patient_ref=patient_ref, previous=None, current=row_dict(row), reason=payload.reason, risk="amber")
    session.add(row); session.commit(); session.refresh(row)
    return {"problem": row_dict(row)}


@router.post("/patients/{patient_ref}/allergies")
def add_allergy(patient_ref: str, payload: AllergyCreate, session: Session = Depends(get_session), auth: AuthContext = Depends(require_roles(*CLINICAL_ROLES))) -> dict[str, Any]:
    require_patient(session, patient_ref)
    severity = payload.severity.lower()
    if severity not in {"green", "amber", "red"}:
        raise HTTPException(status_code=422, detail="severity must be green, amber or red")
    row = PatientAllergyV8(allergy_ref=new_ref("allergy"), patient_ref=patient_ref, substance_ref=payload.substance_ref, substance_name=payload.substance_name, reaction=payload.reaction, severity=severity, confirmed=payload.confirmed, recorded_by_subject=auth.subject)
    session.add(row)
    row.evidence_event_ref = record_evidence(session, entity_type="allergy", entity_ref=row.allergy_ref, action="create", episode_ref=None, patient_ref=patient_ref, previous=None, current=row_dict(row), reason=payload.reason, risk=severity, domain="medication")
    session.add(row); session.commit(); session.refresh(row)
    return {"allergy": row_dict(row)}


@router.post("/patients/{patient_ref}/weights")
def add_weight(patient_ref: str, payload: WeightCreate, session: Session = Depends(get_session), auth: AuthContext = Depends(require_roles(*CLINICAL_ROLES))) -> dict[str, Any]:
    require_patient(session, patient_ref)
    if payload.weight_kg <= 0 or payload.weight_kg > 500:
        raise HTTPException(status_code=422, detail="weight_kg is outside a plausible range")
    row = PatientWeightV8(weight_ref=new_ref("weight"), patient_ref=patient_ref, episode_ref=payload.episode_ref, weight_kg=payload.weight_kg, body_condition_score=payload.body_condition_score, measured_at=payload.measured_at or utc_now(), measured_by_subject=auth.subject)
    session.add(row)
    row.evidence_event_ref = record_evidence(session, entity_type="weight", entity_ref=row.weight_ref, action="record", episode_ref=payload.episode_ref, patient_ref=patient_ref, previous=None, current=row_dict(row), reason=payload.reason, risk="green")
    session.add(row); session.commit(); session.refresh(row)
    return {"weight": row_dict(row)}


@router.post("/episodes/{episode_ref}/encounters")
def create_encounter(episode_ref: str, payload: EncounterCreate, session: Session = Depends(get_session), auth: AuthContext = Depends(require_roles(*CLINICAL_ROLES))) -> dict[str, Any]:
    episode = require_episode(session, episode_ref); require_patient(session, payload.patient_ref)
    if episode.patient_ref and episode.patient_ref != payload.patient_ref:
        raise HTTPException(status_code=409, detail="patient does not match canonical episode")
    row = ClinicalEncounterV8(encounter_ref=new_ref("encounter"), patient_ref=payload.patient_ref, episode_ref=episode_ref, encounter_type=payload.encounter_type, service_ref=payload.service_ref, location_ref=payload.location_ref, responsible_clinician_subject=auth.subject, presenting_complaint=payload.presenting_complaint, history=payload.history, examination=payload.examination, assessment=payload.assessment, plan=payload.plan)
    session.add(row)
    row.evidence_event_ref = record_evidence(session, entity_type="encounter", entity_ref=row.encounter_ref, action="create", episode_ref=episode_ref, patient_ref=payload.patient_ref, previous=None, current=row_dict(row), reason=payload.reason, risk="amber")
    session.add(row); session.commit(); session.refresh(row)
    return {"encounter": row_dict(row)}


@router.post("/episodes/{episode_ref}/notes")
def create_note(episode_ref: str, payload: NoteCreate, session: Session = Depends(get_session), auth: AuthContext = Depends(require_roles(*CLINICAL_ROLES))) -> dict[str, Any]:
    require_episode(session, episode_ref); require_patient(session, payload.patient_ref)
    if payload.supersedes_note_ref:
        prior = session.exec(select(ClinicalNoteV8).where(ClinicalNoteV8.note_ref == payload.supersedes_note_ref)).first()
        if not prior:
            raise HTTPException(status_code=404, detail="superseded note not found")
        prior.status = "superseded"; session.add(prior)
    row = ClinicalNoteV8(note_ref=new_ref("note"), patient_ref=payload.patient_ref, episode_ref=episode_ref, encounter_ref=payload.encounter_ref, note_type=payload.note_type, title=payload.title, body=payload.body, author_subject=auth.subject, author_name=auth.actor_name, supersedes_note_ref=payload.supersedes_note_ref)
    session.add(row)
    row.evidence_event_ref = record_evidence(session, entity_type="clinical_note", entity_ref=row.note_ref, action="sign", episode_ref=episode_ref, patient_ref=payload.patient_ref, previous=None, current={"noteRef": row.note_ref, "type": row.note_type, "status": row.status}, reason=payload.reason, risk="amber")
    session.add(row); session.commit(); session.refresh(row)
    return {"note": row_dict(row)}


@router.put("/formulary/medicines/{medicine_ref}")
def upsert_medicine(medicine_ref: str, payload: MedicineUpsert, session: Session = Depends(get_session), auth: AuthContext = Depends(require_roles(*SENIOR_ROLES))) -> dict[str, Any]:
    row = session.exec(select(FormularyMedicineV8).where(FormularyMedicineV8.medicine_ref == medicine_ref)).first()
    previous = row_dict(row) if row else None
    if row:
        require_expected(row.version, payload.expected_version, "formulary medicine"); row.version += 1
    else:
        row = FormularyMedicineV8(medicine_ref=medicine_ref, generic_name=payload.generic_name)
    for field in ("generic_name", "brand_names", "controlled_schedule", "high_risk", "antimicrobial_class", "routes", "contraindications", "interactions", "status"):
        setattr(row, field, getattr(payload, field))
    if payload.status == "approved":
        row.approved_by_subject = auth.subject; row.approved_at = utc_now()
    session.add(row)
    row.evidence_event_ref = record_evidence(session, entity_type="formulary_medicine", entity_ref=medicine_ref, action="upsert", episode_ref=None, patient_ref=None, previous=previous, current=row_dict(row), reason=payload.reason, risk="amber", domain="medication")
    session.add(row); session.commit(); session.refresh(row)
    return {"medicine": row_dict(row)}


@router.put("/formulary/dose-rules/{rule_ref}")
def upsert_dose_rule(rule_ref: str, payload: DoseRuleUpsert, session: Session = Depends(get_session), auth: AuthContext = Depends(require_roles(*SENIOR_ROLES))) -> dict[str, Any]:
    medicine = session.exec(select(FormularyMedicineV8).where(FormularyMedicineV8.medicine_ref == payload.medicine_ref)).first()
    if not medicine:
        raise HTTPException(status_code=404, detail="formulary medicine not found")
    row = session.exec(select(FormularyDoseRuleV8).where(FormularyDoseRuleV8.rule_ref == rule_ref)).first()
    previous = row_dict(row) if row else None
    if row:
        require_expected(row.version, payload.expected_version, "dose rule"); row.version += 1
    else:
        row = FormularyDoseRuleV8(rule_ref=rule_ref, medicine_ref=payload.medicine_ref, species=payload.species, indication=payload.indication, route=payload.route, source_reference=payload.source_reference)
    for field in ("medicine_ref", "species", "indication", "route", "minimum_mg_per_kg", "maximum_mg_per_kg", "maximum_single_dose_mg", "minimum_interval_hours", "renal_adjustment", "hepatic_adjustment", "source_reference", "status"):
        setattr(row, field, getattr(payload, field))
    session.add(row)
    row.evidence_event_ref = record_evidence(session, entity_type="formulary_dose_rule", entity_ref=rule_ref, action="upsert", episode_ref=None, patient_ref=None, previous=previous, current=row_dict(row), reason=payload.reason, risk="amber", domain="medication")
    session.add(row); session.commit(); session.refresh(row)
    return {"rule": row_dict(row)}


@router.post("/episodes/{episode_ref}/medication-safety-check")
def medication_safety_check(episode_ref: str, payload: MedicationSafetyRequest, session: Session = Depends(get_session), auth: AuthContext = Depends(require_roles(*PRESCRIBER_ROLES))) -> dict[str, Any]:
    require_episode(session, episode_ref)
    patient = require_patient(session, payload.patient_ref)
    medicine = session.exec(select(FormularyMedicineV8).where(FormularyMedicineV8.medicine_ref == payload.medicine_ref)).first()
    if not medicine:
        raise HTTPException(status_code=404, detail="formulary medicine not found")
    latest_weight = session.exec(select(PatientWeightV8).where(PatientWeightV8.patient_ref == payload.patient_ref).order_by(PatientWeightV8.measured_at.desc())).first()
    if not latest_weight:
        raise HTTPException(status_code=409, detail="current patient weight is required before dose review")
    mg_per_kg = payload.dose_mg / latest_weight.weight_kg
    warnings: list[dict[str, Any]] = []
    active_allergies = session.exec(select(PatientAllergyV8).where(PatientAllergyV8.patient_ref == payload.patient_ref, PatientAllergyV8.status == "active")).all()
    for allergy in active_allergies:
        if (allergy.substance_ref and allergy.substance_ref.lower() == payload.medicine_ref.lower()) or allergy.substance_name.lower() in {medicine.generic_name.lower(), payload.medicine_ref.lower()}:
            warnings.append({"code": "allergy_match", "severity": allergy.severity, "message": f"Active allergy: {allergy.substance_name} — {allergy.reaction}"})
    rules = session.exec(select(FormularyDoseRuleV8).where(FormularyDoseRuleV8.medicine_ref == payload.medicine_ref, FormularyDoseRuleV8.species == patient.species, FormularyDoseRuleV8.route == payload.route, FormularyDoseRuleV8.status == "approved")).all()
    matching = [rule for rule in rules if rule.indication.lower() == payload.indication.lower()]
    if medicine.status != "approved":
        warnings.append({"code": "medicine_not_approved", "severity": "red", "message": "Medicine is not approved in the local formulary"})
    if not matching:
        warnings.append({"code": "no_approved_dose_rule", "severity": "red", "message": "No approved species/route/indication dose rule"})
    for rule in matching:
        if rule.minimum_mg_per_kg is not None and mg_per_kg < rule.minimum_mg_per_kg:
            warnings.append({"code": "dose_below_rule", "severity": "amber", "message": f"Calculated {mg_per_kg:.3f} mg/kg is below {rule.minimum_mg_per_kg} mg/kg"})
        if rule.maximum_mg_per_kg is not None and mg_per_kg > rule.maximum_mg_per_kg:
            warnings.append({"code": "dose_above_rule", "severity": "red", "message": f"Calculated {mg_per_kg:.3f} mg/kg exceeds {rule.maximum_mg_per_kg} mg/kg"})
        if rule.maximum_single_dose_mg is not None and payload.dose_mg > rule.maximum_single_dose_mg:
            warnings.append({"code": "single_dose_limit", "severity": "red", "message": f"Dose exceeds maximum single dose {rule.maximum_single_dose_mg} mg"})
        if rule.minimum_interval_hours is not None and payload.interval_hours is not None and payload.interval_hours < rule.minimum_interval_hours:
            warnings.append({"code": "interval_too_short", "severity": "red", "message": f"Interval is shorter than {rule.minimum_interval_hours} hours"})
    blocks = any(item["severity"] == "red" for item in warnings)
    row = MedicationSafetyReviewV8(review_ref=new_ref("med-safety"), patient_ref=payload.patient_ref, episode_ref=episode_ref, medicine_ref=payload.medicine_ref, proposed_dose_mg=payload.dose_mg, proposed_route=payload.route, proposed_interval_hours=payload.interval_hours, weight_kg=latest_weight.weight_kg, calculated_mg_per_kg=mg_per_kg, outcome="blocked" if blocks else "pass_with_warning" if warnings else "passed", warnings=warnings, blocks_order=blocks, reviewed_by_subject=auth.subject)
    session.add(row)
    risk = "red" if blocks else "amber" if warnings else "green"
    row.evidence_event_ref = record_evidence(session, entity_type="medication_safety_review", entity_ref=row.review_ref, action="complete", episode_ref=episode_ref, patient_ref=payload.patient_ref, previous=None, current=row_dict(row), reason=payload.reason, risk=risk, domain="medication")
    session.add(row); session.commit(); session.refresh(row)
    return {"review": row_dict(row)}


@router.post("/episodes/{episode_ref}/anaesthesia/charts")
def create_anaesthesia_chart(episode_ref: str, payload: AnaesthesiaChartCreate, session: Session = Depends(get_session), auth: AuthContext = Depends(require_roles(*PRESCRIBER_ROLES))) -> dict[str, Any]:
    require_episode(session, episode_ref); require_patient(session, payload.patient_ref)
    row = AnaesthesiaChartV8(chart_ref=new_ref("ana-chart"), patient_ref=payload.patient_ref, episode_ref=episode_ref, procedure_ref=payload.procedure_ref, responsible_clinician_subject=auth.subject, anaesthetist_subject=payload.anaesthetist_subject, asa_status=payload.asa_status, pre_anaesthetic_assessment=payload.pre_anaesthetic_assessment, machine_check=payload.machine_check, airway_plan=payload.airway_plan, analgesia_plan=payload.analgesia_plan, ventilation_plan=payload.ventilation_plan)
    session.add(row)
    incomplete = [key for key in ("patient_identity", "consent", "machine", "airway") if not row.machine_check.get(key) and key in {"machine"}]
    risk = "amber" if incomplete or not row.airway_plan else "green"
    row.evidence_event_ref = record_evidence(session, entity_type="anaesthesia_chart", entity_ref=row.chart_ref, action="create", episode_ref=episode_ref, patient_ref=payload.patient_ref, previous=None, current=row_dict(row), reason=payload.reason, risk=risk, domain="anaesthesia")
    session.add(row); session.commit(); session.refresh(row)
    return {"chart": row_dict(row)}


def anaesthesia_concern(payload: AnaesthesiaObservationCreate) -> tuple[str, list[str]]:
    red: list[str] = []; amber: list[str] = []
    if payload.mean_bp is not None and payload.mean_bp < 50: red.append("mean arterial pressure below 50")
    elif payload.mean_bp is not None and payload.mean_bp < 60: amber.append("mean arterial pressure below 60")
    if payload.spo2 is not None and payload.spo2 < 90: red.append("SpO2 below 90%")
    elif payload.spo2 is not None and payload.spo2 < 94: amber.append("SpO2 below 94%")
    if payload.etco2 is not None and (payload.etco2 < 25 or payload.etco2 > 65): red.append("ETCO2 critically outside configured range")
    elif payload.etco2 is not None and (payload.etco2 < 30 or payload.etco2 > 55): amber.append("ETCO2 outside configured range")
    if payload.temperature_c is not None and (payload.temperature_c < 35 or payload.temperature_c > 40): red.append("temperature critically outside configured range")
    elif payload.temperature_c is not None and (payload.temperature_c < 36 or payload.temperature_c > 39.5): amber.append("temperature outside configured range")
    return ("red", red) if red else ("amber", amber) if amber else ("green", [])


@router.post("/anaesthesia/charts/{chart_ref}/observations")
def add_anaesthesia_observation(chart_ref: str, payload: AnaesthesiaObservationCreate, session: Session = Depends(get_session), auth: AuthContext = Depends(require_roles(*CLINICAL_ROLES))) -> dict[str, Any]:
    chart = session.exec(select(AnaesthesiaChartV8).where(AnaesthesiaChartV8.chart_ref == chart_ref)).first()
    if not chart: raise HTTPException(status_code=404, detail="anaesthesia chart not found")
    concern, reasons = anaesthesia_concern(payload)
    row = AnaesthesiaObservationV8(observation_ref=new_ref("ana-obs"), chart_ref=chart_ref, recorded_at=payload.recorded_at or utc_now(), heart_rate=payload.heart_rate, respiratory_rate=payload.respiratory_rate, systolic_bp=payload.systolic_bp, mean_bp=payload.mean_bp, diastolic_bp=payload.diastolic_bp, spo2=payload.spo2, etco2=payload.etco2, temperature_c=payload.temperature_c, anaesthetic_agent_percent=payload.anaesthetic_agent_percent, oxygen_flow_l_min=payload.oxygen_flow_l_min, ventilator_settings=payload.ventilator_settings, concern_level=concern, recorded_by_subject=auth.subject)
    session.add(row)
    row.evidence_event_ref = record_evidence(session, entity_type="anaesthesia_observation", entity_ref=row.observation_ref, action="record", episode_ref=chart.episode_ref, patient_ref=chart.patient_ref, previous=None, current={**row_dict(row), "alertReasons": reasons}, reason=payload.reason, risk=concern, domain="anaesthesia")
    session.add(row); session.commit(); session.refresh(row)
    return {"observation": row_dict(row), "alertReasons": reasons}


@router.post("/anaesthesia/charts/{chart_ref}/drug-events")
def add_anaesthesia_drug(chart_ref: str, payload: AnaesthesiaDrugCreate, session: Session = Depends(get_session), auth: AuthContext = Depends(require_roles(*CLINICAL_ROLES))) -> dict[str, Any]:
    chart = session.exec(select(AnaesthesiaChartV8).where(AnaesthesiaChartV8.chart_ref == chart_ref)).first()
    if not chart: raise HTTPException(status_code=404, detail="anaesthesia chart not found")
    medicine = session.exec(select(FormularyMedicineV8).where(FormularyMedicineV8.medicine_ref == payload.medicine_ref)).first()
    witness_required = bool(medicine and (medicine.high_risk or medicine.controlled_schedule))
    if witness_required and not payload.witness_subject:
        raise HTTPException(status_code=409, detail="high-risk or controlled anaesthesia drug requires a witness")
    row = AnaesthesiaDrugEventV8(drug_event_ref=new_ref("ana-drug"), chart_ref=chart_ref, medicine_ref=payload.medicine_ref, medicine_name=payload.medicine_name, dose=payload.dose, route=payload.route, event_type=payload.event_type, occurred_at=payload.occurred_at or utc_now(), actor_subject=auth.subject, witness_subject=payload.witness_subject)
    session.add(row)
    row.evidence_event_ref = record_evidence(session, entity_type="anaesthesia_drug", entity_ref=row.drug_event_ref, action="record", episode_ref=chart.episode_ref, patient_ref=chart.patient_ref, previous=None, current=row_dict(row), reason=payload.reason, risk="amber" if witness_required else "green", domain="anaesthesia")
    session.add(row); session.commit(); session.refresh(row)
    return {"drugEvent": row_dict(row)}


@router.post("/episodes/{episode_ref}/fluid-plans")
def create_fluid_plan(episode_ref: str, payload: FluidPlanCreate, session: Session = Depends(get_session), auth: AuthContext = Depends(require_roles(*PRESCRIBER_ROLES))) -> dict[str, Any]:
    require_episode(session, episode_ref); require_patient(session, payload.patient_ref)
    if payload.rate_ml_per_hour <= 0: raise HTTPException(status_code=422, detail="fluid rate must be positive")
    row = FluidPlanV8(plan_ref=new_ref("fluid-plan"), patient_ref=payload.patient_ref, episode_ref=episode_ref, fluid_type=payload.fluid_type, route=payload.route, rate_ml_per_hour=payload.rate_ml_per_hour, target_total_ml=payload.target_total_ml, starts_at=payload.starts_at or utc_now(), ends_at=payload.ends_at, indication=payload.indication, prescriber_subject=auth.subject)
    session.add(row)
    row.evidence_event_ref = record_evidence(session, entity_type="fluid_plan", entity_ref=row.plan_ref, action="prescribe", episode_ref=episode_ref, patient_ref=payload.patient_ref, previous=None, current=row_dict(row), reason=payload.reason, risk="amber", domain="inpatient_care")
    session.add(row); session.commit(); session.refresh(row)
    return {"plan": row_dict(row)}


@router.post("/episodes/{episode_ref}/fluid-balance")
def add_fluid_entry(episode_ref: str, payload: FluidEntryCreate, session: Session = Depends(get_session), auth: AuthContext = Depends(require_roles(*CLINICAL_ROLES))) -> dict[str, Any]:
    require_episode(session, episode_ref); require_patient(session, payload.patient_ref)
    if payload.volume_ml <= 0: raise HTTPException(status_code=422, detail="volume must be positive")
    if payload.entry_type not in {"input", "output", "loss", "bolus"}: raise HTTPException(status_code=422, detail="unsupported fluid entry type")
    row = FluidBalanceEntryV8(entry_ref=new_ref("fluid-entry"), patient_ref=payload.patient_ref, episode_ref=episode_ref, plan_ref=payload.plan_ref, entry_type=payload.entry_type, volume_ml=payload.volume_ml, route_or_source=payload.route_or_source, occurred_at=payload.occurred_at or utc_now(), actor_subject=auth.subject)
    session.add(row)
    row.evidence_event_ref = record_evidence(session, entity_type="fluid_balance", entity_ref=row.entry_ref, action="record", episode_ref=episode_ref, patient_ref=payload.patient_ref, previous=None, current=row_dict(row), reason=payload.reason, risk="green", domain="inpatient_care")
    session.add(row); session.commit(); session.refresh(row)
    entries = session.exec(select(FluidBalanceEntryV8).where(FluidBalanceEntryV8.episode_ref == episode_ref)).all()
    total_in = sum(item.volume_ml for item in entries if item.entry_type in {"input", "bolus"})
    total_out = sum(item.volume_ml for item in entries if item.entry_type in {"output", "loss"})
    return {"entry": row_dict(row), "balance": {"totalInputMl": total_in, "totalOutputMl": total_out, "netMl": total_in - total_out}}


@router.post("/episodes/{episode_ref}/care-plans")
def create_care_plan(episode_ref: str, payload: CarePlanCreate, session: Session = Depends(get_session), auth: AuthContext = Depends(require_roles(*CLINICAL_ROLES))) -> dict[str, Any]:
    require_episode(session, episode_ref); require_patient(session, payload.patient_ref)
    row = InpatientCarePlanV8(care_plan_ref=new_ref("care-plan"), patient_ref=payload.patient_ref, episode_ref=episode_ref, area_ref=payload.area_ref, acuity=payload.acuity, goals=payload.goals, interventions=payload.interventions, observation_schedule=payload.observation_schedule, nutrition_plan=payload.nutrition_plan, mobility_plan=payload.mobility_plan, responsible_nurse_subject=payload.responsible_nurse_subject)
    session.add(row)
    row.evidence_event_ref = record_evidence(session, entity_type="care_plan", entity_ref=row.care_plan_ref, action="create", episode_ref=episode_ref, patient_ref=payload.patient_ref, previous=None, current=row_dict(row), reason=payload.reason, risk="amber", domain="inpatient_care")
    session.add(row); session.commit(); session.refresh(row)
    return {"carePlan": row_dict(row)}


@router.post("/care-plans/{care_plan_ref}/entries")
def add_chart_entry(care_plan_ref: str, payload: ChartEntryCreate, session: Session = Depends(get_session), auth: AuthContext = Depends(require_roles(*CLINICAL_ROLES))) -> dict[str, Any]:
    care = session.exec(select(InpatientCarePlanV8).where(InpatientCarePlanV8.care_plan_ref == care_plan_ref)).first()
    if not care: raise HTTPException(status_code=404, detail="care plan not found")
    if payload.concern_level not in {"green", "amber", "red"}: raise HTTPException(status_code=422, detail="invalid concern level")
    row = InpatientChartEntryV8(entry_ref=new_ref("chart-entry"), care_plan_ref=care_plan_ref, patient_ref=care.patient_ref, episode_ref=care.episode_ref, entry_type=payload.entry_type, values=payload.values, concern_level=payload.concern_level, note=payload.note, recorded_at=payload.recorded_at or utc_now(), recorded_by_subject=auth.subject)
    session.add(row)
    row.evidence_event_ref = record_evidence(session, entity_type="inpatient_chart", entity_ref=row.entry_ref, action="record", episode_ref=care.episode_ref, patient_ref=care.patient_ref, previous=None, current=row_dict(row), reason=payload.reason, risk=payload.concern_level, domain="inpatient_care")
    session.add(row); session.commit(); session.refresh(row)
    return {"entry": row_dict(row)}


@router.post("/episodes/{episode_ref}/procedures")
def create_procedure(episode_ref: str, payload: ProcedureCreate, session: Session = Depends(get_session), auth: AuthContext = Depends(require_roles(*PRESCRIBER_ROLES))) -> dict[str, Any]:
    require_episode(session, episode_ref); require_patient(session, payload.patient_ref)
    if payload.status == "completed" and (not payload.findings or not payload.technique):
        raise HTTPException(status_code=409, detail="completed procedure requires findings and technique")
    row = ProcedureRecordV8(procedure_ref=new_ref("procedure"), patient_ref=payload.patient_ref, episode_ref=episode_ref, block_ref=payload.block_ref, procedure_name=payload.procedure_name, lead_clinician_subject=auth.subject, assistants=payload.assistants, preoperative_diagnosis=payload.preoperative_diagnosis, postoperative_diagnosis=payload.postoperative_diagnosis, findings=payload.findings, technique=payload.technique, complications=payload.complications, specimens=payload.specimens, status=payload.status, started_at=utc_now() if payload.status in {"in_progress", "completed"} else None, completed_at=utc_now() if payload.status == "completed" else None)
    session.add(row)
    risk = "red" if payload.complications else "amber"
    row.evidence_event_ref = record_evidence(session, entity_type="procedure", entity_ref=row.procedure_ref, action="create", episode_ref=episode_ref, patient_ref=payload.patient_ref, previous=None, current=row_dict(row), reason=payload.reason, risk=risk, domain="procedure")
    session.add(row); session.commit(); session.refresh(row)
    return {"procedure": row_dict(row)}


@router.post("/procedures/{procedure_ref}/implants")
def add_implant(procedure_ref: str, payload: ImplantCreate, session: Session = Depends(get_session), auth: AuthContext = Depends(require_roles(*CLINICAL_ROLES))) -> dict[str, Any]:
    procedure = session.exec(select(ProcedureRecordV8).where(ProcedureRecordV8.procedure_ref == procedure_ref)).first()
    if not procedure: raise HTTPException(status_code=404, detail="procedure not found")
    if procedure.patient_ref != payload.patient_ref: raise HTTPException(status_code=409, detail="implant patient does not match procedure")
    if not payload.lot_number and not payload.serial_number:
        raise HTTPException(status_code=409, detail="implant requires lot number or serial number")
    row = ImplantTraceV8(implant_ref=new_ref("implant"), procedure_ref=procedure_ref, patient_ref=payload.patient_ref, product_name=payload.product_name, manufacturer=payload.manufacturer, catalogue_number=payload.catalogue_number, lot_number=payload.lot_number, serial_number=payload.serial_number, expiry_date=payload.expiry_date, actor_subject=auth.subject)
    session.add(row)
    row.evidence_event_ref = record_evidence(session, entity_type="implant", entity_ref=row.implant_ref, action="implant", episode_ref=procedure.episode_ref, patient_ref=payload.patient_ref, previous=None, current=row_dict(row), reason=payload.reason, risk="amber", domain="device_traceability")
    session.add(row); session.commit(); session.refresh(row)
    return {"implant": row_dict(row)}


@router.post("/episodes/{episode_ref}/estimates")
def create_estimate(episode_ref: str, payload: EstimateCreate, session: Session = Depends(get_session), auth: AuthContext = Depends(require_roles(*FINANCIAL_ROLES))) -> dict[str, Any]:
    require_episode(session, episode_ref); require_patient(session, payload.patient_ref)
    if not payload.lines: raise HTTPException(status_code=422, detail="estimate requires at least one line")
    existing = session.exec(select(EstimateV8).where(EstimateV8.episode_ref == episode_ref).order_by(EstimateV8.version.desc())).first()
    version = (existing.version + 1) if existing else 1
    lower = sum(round(line.quantity * line.lower_unit_pence) for line in payload.lines if not line.optional)
    upper = sum(round(line.quantity * line.upper_unit_pence) for line in payload.lines if not line.optional)
    if lower < 0 or upper < lower: raise HTTPException(status_code=422, detail="invalid estimate totals")
    row = EstimateV8(estimate_ref=new_ref("estimate"), patient_ref=payload.patient_ref, episode_ref=episode_ref, version=version, status=payload.status, lower_total_pence=lower, upper_total_pence=upper, authorised_limit_pence=payload.authorised_limit_pence, owner_authorisation_ref=payload.owner_authorisation_ref, reason_for_change=payload.reason_for_change, created_by_subject=auth.subject)
    if payload.status in {"issued", "approved"} and not payload.owner_authorisation_ref:
        raise HTTPException(status_code=409, detail="issued or approved estimate requires owner authorisation evidence")
    session.add(row); session.flush()
    line_rows = []
    for item in payload.lines:
        line = EstimateLineV8(line_ref=new_ref("estimate-line"), estimate_ref=row.estimate_ref, **item.model_dump())
        session.add(line); line_rows.append(line)
    row.evidence_event_ref = record_evidence(session, entity_type="estimate", entity_ref=row.estimate_ref, action="create_version", episode_ref=episode_ref, patient_ref=payload.patient_ref, previous=row_dict(existing) if existing else None, current={**row_dict(row), "lines": [row_dict(item) for item in line_rows]}, reason=payload.reason, risk="amber", domain="financial_consent")
    session.add(row); session.commit(); session.refresh(row)
    return {"estimate": row_dict(row), "lines": [row_dict(item) for item in line_rows]}


@router.post("/episodes/{episode_ref}/insurance")
def create_insurance(episode_ref: str, payload: InsuranceCreate, session: Session = Depends(get_session), auth: AuthContext = Depends(require_roles(*FINANCIAL_ROLES))) -> dict[str, Any]:
    require_episode(session, episode_ref); require_patient(session, payload.patient_ref)
    shortfall = None
    latest_estimate = session.exec(select(EstimateV8).where(EstimateV8.episode_ref == episode_ref).order_by(EstimateV8.version.desc())).first()
    if latest_estimate and payload.preauthorised_pence is not None:
        shortfall = max(0, latest_estimate.upper_total_pence - payload.preauthorised_pence)
    row = InsuranceCaseV8(insurance_ref=new_ref("insurance"), patient_ref=payload.patient_ref, episode_ref=episode_ref, owner_ref=payload.owner_ref, insurer_name=payload.insurer_name, policy_number_masked=payload.policy_number_masked, claim_reference=payload.claim_reference, cover_limit_pence=payload.cover_limit_pence, excess_pence=payload.excess_pence, preauthorised_pence=payload.preauthorised_pence, direct_claim_requested=payload.direct_claim_requested, status=payload.status, shortfall_pence=shortfall)
    session.add(row)
    row.evidence_event_ref = record_evidence(session, entity_type="insurance", entity_ref=row.insurance_ref, action="create", episode_ref=episode_ref, patient_ref=payload.patient_ref, previous=None, current=row_dict(row), reason=payload.reason, risk="amber", domain="insurance")
    session.add(row); session.commit(); session.refresh(row)
    return {"insurance": row_dict(row)}


@router.post("/episodes/{episode_ref}/transactions")
def create_transaction(episode_ref: str, payload: TransactionCreate, session: Session = Depends(get_session), auth: AuthContext = Depends(require_roles(*FINANCIAL_ROLES))) -> dict[str, Any]:
    require_episode(session, episode_ref); require_patient(session, payload.patient_ref)
    if payload.amount_pence == 0: raise HTTPException(status_code=422, detail="transaction amount cannot be zero")
    row = FinancialTransactionV8(transaction_ref=new_ref("transaction"), patient_ref=payload.patient_ref, episode_ref=episode_ref, owner_ref=payload.owner_ref, transaction_type=payload.transaction_type, amount_pence=payload.amount_pence, payment_method=payload.payment_method, external_reference=payload.external_reference, status=payload.status, actor_subject=auth.subject)
    session.add(row)
    row.evidence_event_ref = record_evidence(session, entity_type="financial_transaction", entity_ref=row.transaction_ref, action="record", episode_ref=episode_ref, patient_ref=payload.patient_ref, previous=None, current=row_dict(row), reason=payload.reason, risk="amber", domain="financial")
    session.add(row); session.commit(); session.refresh(row)
    return {"transaction": row_dict(row)}


@router.post("/episodes/{episode_ref}/communications")
def create_communication(episode_ref: str, payload: CommunicationCreate, session: Session = Depends(get_session), auth: AuthContext = Depends(require_authenticated)) -> dict[str, Any]:
    require_episode(session, episode_ref); require_patient(session, payload.patient_ref)
    if payload.audience in {"owner", "referring_vet"} and not payload.summary.strip():
        raise HTTPException(status_code=422, detail="communication summary is required")
    row = CommunicationEventV8(communication_ref=new_ref("communication"), patient_ref=payload.patient_ref, episode_ref=episode_ref, owner_ref=payload.owner_ref, audience=payload.audience, channel=payload.channel, direction=payload.direction, subject=payload.subject, summary=payload.summary, outcome=payload.outcome, consent_or_authorisation=payload.consent_or_authorisation, attachments=payload.attachments, occurred_at=payload.occurred_at or utc_now(), actor_subject=auth.subject)
    session.add(row)
    risk = "amber" if payload.consent_or_authorisation else "green"
    row.evidence_event_ref = record_evidence(session, entity_type="communication", entity_ref=row.communication_ref, action="record", episode_ref=episode_ref, patient_ref=payload.patient_ref, previous=None, current=row_dict(row), reason=payload.reason, risk=risk, domain="client_communication")
    session.add(row); session.commit(); session.refresh(row)
    return {"communication": row_dict(row)}


def build_document_content(session: Session, episode_ref: str, patient: PatientClinicalRecordV8, document_type: str, additional_text: str) -> tuple[str, dict[str, Any]]:
    encounter = session.exec(select(ClinicalEncounterV8).where(ClinicalEncounterV8.episode_ref == episode_ref).order_by(ClinicalEncounterV8.started_at.desc())).first()
    problems = session.exec(select(PatientProblemV8).where(PatientProblemV8.patient_ref == patient.patient_ref, PatientProblemV8.status == "active")).all()
    medications = session.exec(select(MedicationOrder).where(MedicationOrder.episode_ref == episode_ref, MedicationOrder.status == "active")).all()
    procedures = session.exec(select(ProcedureRecordV8).where(ProcedureRecordV8.episode_ref == episode_ref)).all()
    latest_estimate = session.exec(select(EstimateV8).where(EstimateV8.episode_ref == episode_ref).order_by(EstimateV8.version.desc())).first()
    lines = [f"# {document_type.replace('_', ' ').title()}", "", f"**Patient:** {patient.display_name}", f"**Species:** {patient.species}", f"**Patient reference:** {patient.patient_ref}", f"**Episode:** {episode_ref}", ""]
    if encounter:
        lines.extend(["## Clinical summary", encounter.assessment or encounter.history or encounter.presenting_complaint, "", "## Plan", encounter.plan or "Not recorded", ""])
    if problems:
        lines.extend(["## Active problems", *[f"- {item.title}: {item.description}" for item in problems], ""])
    if procedures:
        lines.extend(["## Procedures", *[f"- {item.procedure_name} — {item.status}: {item.findings}" for item in procedures], ""])
    if medications:
        lines.extend(["## Current medication", *[f"- {item.medication_name}: {item.dose} {item.route} {item.frequency}" for item in medications], ""])
    if latest_estimate:
        lines.extend(["## Latest estimate", f"£{latest_estimate.lower_total_pence / 100:,.2f}–£{latest_estimate.upper_total_pence / 100:,.2f}", ""])
    if additional_text.strip(): lines.extend(["## Additional information", additional_text.strip(), ""])
    source = {"encounterRef": encounter.encounter_ref if encounter else None, "problemRefs": [item.problem_ref for item in problems], "procedureRefs": [item.procedure_ref for item in procedures], "medicationOrderRefs": [item.order_ref for item in medications], "estimateRef": latest_estimate.estimate_ref if latest_estimate else None}
    return "\n".join(lines).strip(), source


@router.post("/episodes/{episode_ref}/documents/generate")
def generate_document(episode_ref: str, payload: DocumentGenerate, session: Session = Depends(get_session), auth: AuthContext = Depends(require_roles(*DOCUMENT_APPROVER_ROLES))) -> dict[str, Any]:
    require_episode(session, episode_ref); patient = require_patient(session, payload.patient_ref)
    content, source = build_document_content(session, episode_ref, patient, payload.document_type, payload.additional_text)
    row = ClinicalDocumentV8(document_ref=new_ref("document"), patient_ref=payload.patient_ref, episode_ref=episode_ref, document_type=payload.document_type, title=payload.title or payload.document_type.replace("_", " ").title(), content=content, generated_from=source, author_subject=auth.subject)
    session.add(row)
    row.evidence_event_ref = record_evidence(session, entity_type="clinical_document", entity_ref=row.document_ref, action="generate", episode_ref=episode_ref, patient_ref=payload.patient_ref, previous=None, current={"documentRef": row.document_ref, "documentType": row.document_type, "source": source, "status": row.status}, reason=payload.reason, risk="amber", domain="clinical_documentation")
    session.add(row); session.commit(); session.refresh(row)
    return {"document": row_dict(row)}


@router.get("/episodes/{episode_ref}/record")
def episode_record(episode_ref: str, session: Session = Depends(get_session), auth: AuthContext = Depends(require_authenticated)) -> dict[str, Any]:
    episode = require_episode(session, episode_ref)
    patient_ref = episode.patient_ref
    patient = session.exec(select(PatientClinicalRecordV8).where(PatientClinicalRecordV8.patient_ref == patient_ref)).first() if patient_ref else None
    def rows(model: Any, field: Any) -> list[dict[str, Any]]:
        return [row_dict(row) for row in session.exec(select(model).where(field == episode_ref)).all()]
    owner_links = [row_dict(row) for row in session.exec(select(PatientOwnerLinkV8).where(PatientOwnerLinkV8.patient_ref == patient_ref, PatientOwnerLinkV8.active == True)).all()] if patient_ref else []  # noqa: E712
    owners = []
    for link in owner_links:
        owner = session.exec(select(OwnerAccountV8).where(OwnerAccountV8.owner_ref == link["owner_ref"])).first()
        if owner: owners.append(row_dict(owner))
    fluid_entries = session.exec(select(FluidBalanceEntryV8).where(FluidBalanceEntryV8.episode_ref == episode_ref)).all()
    total_in = sum(item.volume_ml for item in fluid_entries if item.entry_type in {"input", "bolus"})
    total_out = sum(item.volume_ml for item in fluid_entries if item.entry_type in {"output", "loss"})
    estimates = rows(EstimateV8, EstimateV8.episode_ref)
    transactions = rows(FinancialTransactionV8, FinancialTransactionV8.episode_ref)
    charged = sum(item["amount_pence"] for item in transactions if item["transaction_type"] in {"charge", "invoice"})
    paid = sum(item["amount_pence"] for item in transactions if item["transaction_type"] in {"payment", "credit"})
    return {
        "episode": episode.model_dump(mode="json"), "patient": row_dict(patient) if patient else None, "owners": owners,
        "ownerLinks": owner_links, "encounters": rows(ClinicalEncounterV8, ClinicalEncounterV8.episode_ref),
        "notes": rows(ClinicalNoteV8, ClinicalNoteV8.episode_ref),
        "problems": [row_dict(row) for row in session.exec(select(PatientProblemV8).where(PatientProblemV8.patient_ref == patient_ref)).all()] if patient_ref else [],
        "allergies": [row_dict(row) for row in session.exec(select(PatientAllergyV8).where(PatientAllergyV8.patient_ref == patient_ref)).all()] if patient_ref else [],
        "weights": [row_dict(row) for row in session.exec(select(PatientWeightV8).where(PatientWeightV8.patient_ref == patient_ref).order_by(PatientWeightV8.measured_at.desc())).all()] if patient_ref else [],
        "medicationSafetyReviews": rows(MedicationSafetyReviewV8, MedicationSafetyReviewV8.episode_ref),
        "anaesthesiaCharts": rows(AnaesthesiaChartV8, AnaesthesiaChartV8.episode_ref),
        "fluidPlans": rows(FluidPlanV8, FluidPlanV8.episode_ref),
        "fluidBalanceEntries": [row_dict(row) for row in fluid_entries], "fluidBalance": {"totalInputMl": total_in, "totalOutputMl": total_out, "netMl": total_in - total_out},
        "carePlans": rows(InpatientCarePlanV8, InpatientCarePlanV8.episode_ref), "procedures": rows(ProcedureRecordV8, ProcedureRecordV8.episode_ref),
        "estimates": estimates, "insurance": rows(InsuranceCaseV8, InsuranceCaseV8.episode_ref), "transactions": transactions,
        "financialSummary": {"chargedPence": charged, "paidPence": paid, "balancePence": charged - paid},
        "communications": rows(CommunicationEventV8, CommunicationEventV8.episode_ref), "documents": rows(ClinicalDocumentV8, ClinicalDocumentV8.episode_ref),
    }


@router.get("/dashboard")
def detailed_dashboard(session: Session = Depends(get_session), auth: AuthContext = Depends(require_authenticated)) -> dict[str, Any]:
    active_patients = len(session.exec(select(PatientClinicalRecordV8).where(PatientClinicalRecordV8.status == "active")).all())
    active_problems = len(session.exec(select(PatientProblemV8).where(PatientProblemV8.status == "active")).all())
    red_allergies = len(session.exec(select(PatientAllergyV8).where(PatientAllergyV8.status == "active", PatientAllergyV8.severity == "red")).all())
    blocked_reviews = len(session.exec(select(MedicationSafetyReviewV8).where(MedicationSafetyReviewV8.blocks_order == True)).all())  # noqa: E712
    red_anaesthesia = len(session.exec(select(AnaesthesiaObservationV8).where(AnaesthesiaObservationV8.concern_level == "red")).all())
    red_inpatient = len(session.exec(select(InpatientChartEntryV8).where(InpatientChartEntryV8.concern_level == "red")).all())
    draft_documents = len(session.exec(select(ClinicalDocumentV8).where(ClinicalDocumentV8.status == "draft")).all())
    open_insurance = len(session.exec(select(InsuranceCaseV8).where(InsuranceCaseV8.status.notin_(["paid", "closed", "declined"]))).all())
    return {"summary": {"activePatients": active_patients, "activeProblems": active_problems, "redAllergies": red_allergies, "blockedMedicationReviews": blocked_reviews, "redAnaesthesiaObservations": red_anaesthesia, "redInpatientEntries": red_inpatient, "draftDocuments": draft_documents, "openInsuranceCases": open_insurance}}
