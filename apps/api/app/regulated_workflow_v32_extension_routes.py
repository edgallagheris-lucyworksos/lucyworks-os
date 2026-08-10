from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field as PydanticField
from sqlmodel import Session, select

from app.auth import AuthContext, CLINICAL_ROLES, require_authenticated, require_roles
from app.database import get_session
from app.detailed_hospital_models import EstimateLineV8, EstimateV8, PatientClinicalRecordV8
from app.evidence_service import create_evidence_event
from app.hospital_ops_models import CanonicalEpisodeState
from app.regulated_workflow_v32_extension_models import ChargeProvenanceV32, ComplaintV32, PrescriptionChoiceV32
from app.regulated_workflow_v32_models import AIProvenanceV32, EstimateGovernanceV32, ServicePriceV32

router = APIRouter(prefix="/api/v32", tags=["regulated-workflow-v32"])
FINANCIAL_ROLES = ("admin", "ops_manager", "hospital_director", "governance_lead")
COMPLAINT_ROLES = ("admin", "ops_manager", "hospital_director", "governance_lead", "clinical_director")
PRESCRIPTION_EVIDENCE_ROLES = tuple(sorted(set(CLINICAL_ROLES) | {"admin", "ops_manager"}))


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_ref(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def row_dict(row: Any) -> dict[str, Any]:
    return row.model_dump(mode="json")


def require_episode_patient(session: Session, episode_ref: str, patient_ref: str) -> CanonicalEpisodeState:
    episode = session.exec(select(CanonicalEpisodeState).where(CanonicalEpisodeState.episode_ref == episode_ref)).first()
    if not episode:
        raise HTTPException(status_code=404, detail="canonical episode not found")
    if episode.patient_ref != patient_ref:
        raise HTTPException(status_code=409, detail="patient does not match canonical episode")
    if not session.exec(select(PatientClinicalRecordV8).where(PatientClinicalRecordV8.patient_ref == patient_ref)).first():
        raise HTTPException(status_code=404, detail="patient record not found")
    return episode


def record_event(
    session: Session,
    auth: AuthContext,
    *,
    action: str,
    entity_type: str,
    entity_ref: str,
    current: dict[str, Any],
    reason: str,
    previous: dict[str, Any] | None = None,
    episode_ref: str | None = None,
    patient_ref: str | None = None,
    risk: str = "amber",
) -> str:
    event, _ = create_evidence_event(
        session,
        event_type=f"v32_{entity_type}_{action}",
        action=action,
        actor_id=auth.actor_id or auth.subject,
        actor_name=auth.actor_name,
        actor_role=auth.role,
        actor_auth_source=auth.auth_source,
        patient_case_id=patient_ref,
        referral_episode_id=episode_ref,
        previous_state=previous,
        new_state=current,
        reason=reason,
        justification="LucyWorks regulated operational evidence",
        evidence_links=[{"type": entity_type, "id": entity_ref}],
        compliance_domain="regulated_workflow",
        risk_level=risk,
        source_module="regulated-workflow-v32",
        source_record_ref=entity_ref,
        correlation_id=episode_ref or entity_ref,
        entity_type=entity_type,
        entity_id=entity_ref,
        idempotency_key=f"v32:{entity_type}:{entity_ref}:{action}:{current.get('version', current.get('status', 'event'))}",
    )
    return event.event_ref


class ChargeCreate(BaseModel):
    patientRef: str
    estimateRef: str | None = None
    estimateLineRef: str | None = None
    servicePriceRef: str | None = None
    category: str
    description: str
    quantity: float = PydanticField(default=1, gt=0)
    unitPence: int = PydanticField(ge=0)
    thirdPartyCostPence: int | None = PydanticField(default=None, ge=0)
    markupPence: int | None = PydanticField(default=None, ge=0)
    externalSupplier: str | None = None
    sourceSystem: str = "lucyworks"
    externalReference: str | None = None
    reason: str = "Charge recorded"


class ComplaintCreate(BaseModel):
    premisesRef: str
    episodeRef: str | None = None
    patientRef: str | None = None
    ownerRef: str | None = None
    channel: str
    category: str
    severity: str = "standard"
    summary: str
    assignedRole: str = "ops_manager"
    assignedSubject: str | None = None
    dueAt: datetime | None = None
    reason: str = "Complaint recorded"


class ComplaintUpdate(BaseModel):
    expectedVersion: int
    status: str
    assignedRole: str | None = None
    assignedSubject: str | None = None
    dueAt: datetime | None = None
    resolution: str | None = None
    reason: str


class PrescriptionChoiceCreate(BaseModel):
    patientRef: str
    ownerRef: str | None = None
    medicationName: str
    medicationRef: str | None = None
    writtenPrescriptionOffered: bool
    prescriptionFeePence: int | None = PydanticField(default=None, ge=0)
    clientChoice: str
    informationDeliveryRef: str | None = None
    ongoingMedicationNoticeRef: str | None = None
    reason: str = "Prescription choice recorded"


@router.post("/episodes/{episode_ref}/charges")
def create_charge(
    episode_ref: str,
    payload: ChargeCreate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*FINANCIAL_ROLES)),
) -> dict[str, Any]:
    require_episode_patient(session, episode_ref, payload.patientRef)
    estimate = None
    estimate_line = None
    service_price = None

    if payload.estimateRef:
        estimate = session.exec(select(EstimateV8).where(EstimateV8.estimate_ref == payload.estimateRef)).first()
        if not estimate or estimate.episode_ref != episode_ref:
            raise HTTPException(status_code=409, detail="charge estimate does not belong to episode")
    if payload.estimateLineRef:
        estimate_line = session.exec(select(EstimateLineV8).where(EstimateLineV8.line_ref == payload.estimateLineRef)).first()
        if not estimate_line or (payload.estimateRef and estimate_line.estimate_ref != payload.estimateRef):
            raise HTTPException(status_code=409, detail="charge estimate line does not match estimate")
    if payload.servicePriceRef:
        service_price = session.exec(select(ServicePriceV32).where(ServicePriceV32.price_ref == payload.servicePriceRef)).first()
        if not service_price:
            raise HTTPException(status_code=404, detail="service price not found")

    gross = round(payload.quantity * payload.unitPence)
    if payload.thirdPartyCostPence is not None or payload.markupPence is not None:
        if payload.thirdPartyCostPence is None or payload.markupPence is None:
            raise HTTPException(status_code=422, detail="third-party cost and markup must be recorded together")
        if payload.thirdPartyCostPence + payload.markupPence != gross:
            raise HTTPException(status_code=409, detail="third-party cost plus markup must equal gross charge")
        if not (payload.externalSupplier or "").strip():
            raise HTTPException(status_code=409, detail="third-party charge requires supplier identity")

    row = ChargeProvenanceV32(
        charge_ref=new_ref("charge"),
        episode_ref=episode_ref,
        patient_ref=payload.patientRef,
        estimate_ref=payload.estimateRef,
        estimate_line_ref=payload.estimateLineRef,
        service_price_ref=payload.servicePriceRef,
        category=payload.category.strip(),
        description=payload.description.strip(),
        quantity=payload.quantity,
        unit_pence=payload.unitPence,
        gross_pence=gross,
        third_party_cost_pence=payload.thirdPartyCostPence,
        markup_pence=payload.markupPence,
        external_supplier=payload.externalSupplier,
        source_system=payload.sourceSystem.strip() or "lucyworks",
        external_reference=payload.externalReference,
        actor_subject=auth.subject,
    )
    if not row.category or not row.description:
        raise HTTPException(status_code=422, detail="charge category and description are required")
    session.add(row)
    session.flush()
    row.evidence_event_ref = record_event(
        session, auth, action="record", entity_type="charge_provenance", entity_ref=row.charge_ref,
        episode_ref=episode_ref, patient_ref=row.patient_ref, current=row_dict(row), reason=payload.reason,
        risk="amber" if row.third_party_cost_pence is not None else "green",
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return {"charge": row_dict(row)}


@router.post("/complaints")
def create_complaint(
    payload: ComplaintCreate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*COMPLAINT_ROLES)),
) -> dict[str, Any]:
    summary = payload.summary.strip()
    if not summary:
        raise HTTPException(status_code=422, detail="complaint summary is required")
    if payload.episodeRef and payload.patientRef:
        require_episode_patient(session, payload.episodeRef, payload.patientRef)
    elif payload.episodeRef or payload.patientRef:
        raise HTTPException(status_code=422, detail="episode and patient references must be supplied together")

    row = ComplaintV32(
        complaint_ref=new_ref("complaint"),
        premises_ref=payload.premisesRef,
        episode_ref=payload.episodeRef,
        patient_ref=payload.patientRef,
        owner_ref=payload.ownerRef,
        channel=payload.channel,
        category=payload.category,
        severity=payload.severity,
        summary=summary,
        assigned_role=payload.assignedRole,
        assigned_subject=payload.assignedSubject,
        due_at=payload.dueAt,
        created_by_subject=auth.subject,
    )
    session.add(row)
    session.flush()
    row.evidence_event_ref = record_event(
        session, auth, action="create", entity_type="complaint", entity_ref=row.complaint_ref,
        episode_ref=row.episode_ref, patient_ref=row.patient_ref, current=row_dict(row), reason=payload.reason,
        risk="red" if row.severity.lower() in {"serious", "critical"} else "amber",
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return {"complaint": row_dict(row)}


@router.patch("/complaints/{complaint_ref}")
def update_complaint(
    complaint_ref: str,
    payload: ComplaintUpdate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*COMPLAINT_ROLES)),
) -> dict[str, Any]:
    query = select(ComplaintV32).where(ComplaintV32.complaint_ref == complaint_ref)
    if session.get_bind().dialect.name == "postgresql":
        query = query.with_for_update()
    row = session.exec(query).first()
    if not row:
        raise HTTPException(status_code=404, detail="complaint not found")
    if row.version != payload.expectedVersion:
        raise HTTPException(status_code=409, detail={"message": "stale complaint", "currentVersion": row.version})
    if payload.status not in {"open", "acknowledged", "investigating", "resolved", "closed"}:
        raise HTTPException(status_code=422, detail="invalid complaint status")
    if payload.status in {"resolved", "closed"} and not (payload.resolution or row.resolution or "").strip():
        raise HTTPException(status_code=409, detail="resolved complaint requires resolution evidence")

    previous = row_dict(row)
    row.status = payload.status
    if payload.assignedRole is not None:
        row.assigned_role = payload.assignedRole
    if payload.assignedSubject is not None:
        row.assigned_subject = payload.assignedSubject
    if payload.dueAt is not None:
        row.due_at = payload.dueAt
    if payload.resolution is not None:
        row.resolution = payload.resolution.strip()
    if payload.status == "acknowledged" and row.acknowledged_at is None:
        row.acknowledged_at = utc_now()
    if payload.status in {"resolved", "closed"}:
        row.resolved_at = row.resolved_at or utc_now()
    row.version += 1
    row.updated_at = utc_now()
    session.add(row)
    session.flush()
    row.evidence_event_ref = record_event(
        session, auth, action=payload.status, entity_type="complaint", entity_ref=row.complaint_ref,
        episode_ref=row.episode_ref, patient_ref=row.patient_ref, previous=previous, current=row_dict(row),
        reason=payload.reason, risk="green" if payload.status in {"resolved", "closed"} else "amber",
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return {"complaint": row_dict(row)}


@router.post("/episodes/{episode_ref}/prescription-choice")
def create_prescription_choice(
    episode_ref: str,
    payload: PrescriptionChoiceCreate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*PRESCRIPTION_EVIDENCE_ROLES)),
) -> dict[str, Any]:
    require_episode_patient(session, episode_ref, payload.patientRef)
    choice = payload.clientChoice.strip().lower()
    allowed = {"hospital_supply", "written_prescription", "declined", "not_applicable"}
    if choice not in allowed:
        raise HTTPException(status_code=422, detail=f"client choice must be one of {sorted(allowed)}")
    if payload.writtenPrescriptionOffered and not payload.informationDeliveryRef:
        raise HTTPException(status_code=409, detail="written-prescription offer requires information-delivery evidence")
    if choice == "written_prescription" and not payload.writtenPrescriptionOffered:
        raise HTTPException(status_code=409, detail="client cannot select written prescription unless it was offered")

    row = PrescriptionChoiceV32(
        choice_ref=new_ref("prescription-choice"),
        episode_ref=episode_ref,
        patient_ref=payload.patientRef,
        owner_ref=payload.ownerRef,
        medication_name=payload.medicationName.strip(),
        medication_ref=payload.medicationRef,
        written_prescription_offered=payload.writtenPrescriptionOffered,
        prescription_fee_pence=payload.prescriptionFeePence,
        client_choice=choice,
        information_delivery_ref=payload.informationDeliveryRef,
        ongoing_medication_notice_ref=payload.ongoingMedicationNoticeRef,
        recorded_by_subject=auth.subject,
    )
    if not row.medication_name:
        raise HTTPException(status_code=422, detail="medication name is required")
    session.add(row)
    session.flush()
    row.evidence_event_ref = record_event(
        session, auth, action="record", entity_type="prescription_choice", entity_ref=row.choice_ref,
        episode_ref=episode_ref, patient_ref=row.patient_ref, current=row_dict(row), reason=payload.reason, risk="green",
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return {"prescriptionChoice": row_dict(row)}


@router.get("/episodes/{episode_ref}/governance")
def episode_governance_snapshot(
    episode_ref: str,
    session: Session = Depends(get_session),
    _: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    episode = session.exec(select(CanonicalEpisodeState).where(CanonicalEpisodeState.episode_ref == episode_ref)).first()
    if not episode:
        raise HTTPException(status_code=404, detail="canonical episode not found")

    estimates = session.exec(select(EstimateGovernanceV32).where(EstimateGovernanceV32.episode_ref == episode_ref).order_by(EstimateGovernanceV32.evaluated_at.desc())).all()
    charges = session.exec(select(ChargeProvenanceV32).where(ChargeProvenanceV32.episode_ref == episode_ref).order_by(ChargeProvenanceV32.created_at.desc())).all()
    prescriptions = session.exec(select(PrescriptionChoiceV32).where(PrescriptionChoiceV32.episode_ref == episode_ref).order_by(PrescriptionChoiceV32.recorded_at.desc())).all()
    complaints = session.exec(select(ComplaintV32).where(ComplaintV32.episode_ref == episode_ref).order_by(ComplaintV32.created_at.desc())).all()
    ai_rows = session.exec(select(AIProvenanceV32).where(AIProvenanceV32.episode_ref == episode_ref).order_by(AIProvenanceV32.generated_at.desc())).all()

    blockers: list[dict[str, Any]] = []
    latest_estimate = estimates[0] if estimates else None
    if latest_estimate and latest_estimate.written_estimate_required and not latest_estimate.written_delivery_ref:
        blockers.append({"code": "estimate_delivery", "severity": "red", "message": "Required written estimate delivery evidence is missing."})
    if latest_estimate and latest_estimate.written_update_required and latest_estimate.status != "evidenced":
        blockers.append({"code": "estimate_update", "severity": "red", "message": "Material estimate increase has not been evidenced."})
    unresolved_ai = [row for row in ai_rows if row.status == "draft"]
    if unresolved_ai:
        blockers.append({"code": "ai_review", "severity": "amber", "message": f"{len(unresolved_ai)} AI-assisted output(s) still require human review."})
    open_complaints = [row for row in complaints if row.status not in {"resolved", "closed"}]

    return {
        "episode": {"episodeRef": episode.episode_ref, "patientRef": episode.patient_ref, "phase": episode.phase, "status": episode.status},
        "summary": {
            "estimateVersions": len(estimates),
            "charges": len(charges),
            "chargeTotalPence": sum(row.gross_pence for row in charges),
            "prescriptionChoices": len(prescriptions),
            "openComplaints": len(open_complaints),
            "unreviewedAI": len(unresolved_ai),
            "blockers": len(blockers),
        },
        "blockers": blockers,
        "latestEstimate": row_dict(latest_estimate) if latest_estimate else None,
        "charges": [row_dict(row) for row in charges],
        "prescriptionChoices": [row_dict(row) for row in prescriptions],
        "complaints": [row_dict(row) for row in complaints],
        "aiProvenance": [row_dict(row) for row in ai_rows],
    }
