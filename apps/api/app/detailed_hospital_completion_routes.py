from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field as PydanticField
from sqlmodel import Session, select

from app.auth import AuthContext, PRESCRIBER_ROLES, SENIOR_ROLES, require_authenticated, require_roles
from app.clinical_execution_models import MedicationAdministration, MedicationOrder
from app.database import get_session
from app.detailed_hospital_models import (
    AnaesthesiaChartV8,
    ClinicalDocumentV8,
    CommunicationEventV8,
    FormularyMedicineV8,
    MedicationSafetyReviewV8,
    PatientProblemV8,
)
from app.detailed_hospital_routes import record_evidence, require_episode, require_patient, row_dict, utc_now

router = APIRouter(prefix="/api/v8", tags=["detailed-hospital-record-v8-completion"])
DOCUMENT_APPROVER_ROLES = set(SENIOR_ROLES) | {"clinician"}


def new_ref(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def normalise(value: Any) -> str:
    return str(value or "").strip().lower()


class MedicationOrderFromReview(BaseModel):
    patient_ref: str
    safety_review_ref: str
    medication_name: str | None = None
    frequency: str
    starts_at: datetime
    ends_at: datetime | None = None
    scheduled_times: list[datetime] = PydanticField(default_factory=list)
    reason: str


class AnaesthesiaTransition(BaseModel):
    expected_version: int
    status: str
    recovery_score: str | None = None
    reason: str


class DocumentApprove(BaseModel):
    expected_version: int
    reason: str


class DocumentSend(BaseModel):
    expected_version: int
    audience: str
    channel: str
    recipient_ref: str | None = None
    owner_ref: str | None = None
    reason: str


def medication_conflicts(session: Session, patient_ref: str, medicine: FormularyMedicineV8) -> list[dict[str, Any]]:
    conflicts: list[dict[str, Any]] = []
    active_orders = session.exec(
        select(MedicationOrder).where(MedicationOrder.patient_ref == patient_ref, MedicationOrder.status == "active")
    ).all()
    active_refs = {normalise(row.medication_ref): row for row in active_orders}
    active_names = {normalise(row.medication_name): row for row in active_orders}
    for item in medicine.interactions or []:
        other_ref = normalise(item.get("medicineRef") or item.get("medicine_ref"))
        other_name = normalise(item.get("medicineName") or item.get("medicine_name"))
        matched = active_refs.get(other_ref) if other_ref else active_names.get(other_name) if other_name else None
        if matched:
            conflicts.append({
                "code": "active_medication_interaction",
                "severity": normalise(item.get("severity")) or "amber",
                "message": item.get("message") or f"Interaction with active medication {matched.medication_name}",
                "activeOrderRef": matched.order_ref,
            })
    active_problems = session.exec(
        select(PatientProblemV8).where(PatientProblemV8.patient_ref == patient_ref, PatientProblemV8.status == "active")
    ).all()
    problem_text = " | ".join(normalise(f"{row.title} {row.description}") for row in active_problems)
    for item in medicine.contraindications or []:
        phrase = normalise(item.get("problemContains") or item.get("problem_contains") or item.get("condition"))
        if phrase and phrase in problem_text:
            conflicts.append({
                "code": "active_problem_contraindication",
                "severity": normalise(item.get("severity")) or "red",
                "message": item.get("message") or f"Contraindication matches active problem: {phrase}",
            })
    return conflicts


@router.post("/episodes/{episode_ref}/medication-orders")
def prescribe_from_safety_review(
    episode_ref: str,
    payload: MedicationOrderFromReview,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*PRESCRIBER_ROLES)),
) -> dict[str, Any]:
    require_episode(session, episode_ref)
    require_patient(session, payload.patient_ref)
    review = session.exec(
        select(MedicationSafetyReviewV8).where(MedicationSafetyReviewV8.review_ref == payload.safety_review_ref)
    ).first()
    if not review:
        raise HTTPException(status_code=404, detail="medication safety review not found")
    if review.episode_ref != episode_ref or review.patient_ref != payload.patient_ref:
        raise HTTPException(status_code=409, detail="safety review does not belong to this patient and episode")
    if review.blocks_order or review.outcome == "blocked":
        raise HTTPException(status_code=409, detail={"message": "medication order blocked by safety review", "warnings": review.warnings})
    medicine = session.exec(
        select(FormularyMedicineV8).where(FormularyMedicineV8.medicine_ref == review.medicine_ref)
    ).first()
    if not medicine or medicine.status != "approved":
        raise HTTPException(status_code=409, detail="medicine is not currently approved in the local formulary")
    conflicts = medication_conflicts(session, payload.patient_ref, medicine)
    red_conflicts = [item for item in conflicts if item["severity"] == "red"]
    if red_conflicts:
        raise HTTPException(status_code=409, detail={"message": "medication order blocked by interaction or contraindication", "warnings": conflicts})
    order_ref = f"order-{review.review_ref}"
    existing = session.exec(select(MedicationOrder).where(MedicationOrder.order_ref == order_ref)).first()
    if existing:
        administrations = session.exec(
            select(MedicationAdministration).where(MedicationAdministration.order_ref == order_ref).order_by(MedicationAdministration.scheduled_at)
        ).all()
        return {"order": row_dict(existing), "administrations": [row_dict(row) for row in administrations], "created": False, "warnings": conflicts}
    times = sorted(set(payload.scheduled_times or [payload.starts_at]))
    if any(item < payload.starts_at for item in times):
        raise HTTPException(status_code=422, detail="scheduled administration cannot precede the order start")
    if payload.ends_at and any(item > payload.ends_at for item in times):
        raise HTTPException(status_code=422, detail="scheduled administration cannot be after the order end")
    row = MedicationOrder(
        order_ref=order_ref,
        episode_ref=episode_ref,
        patient_ref=payload.patient_ref,
        medication_ref=review.medicine_ref,
        medication_name=payload.medication_name or medicine.generic_name,
        dose=f"{review.proposed_dose_mg:g} mg",
        route=review.proposed_route,
        frequency=payload.frequency,
        indication="Safety-reviewed prescription",
        starts_at=payload.starts_at,
        ends_at=payload.ends_at,
        prescriber_subject=auth.subject,
        prescriber_name=auth.actor_name,
        high_risk=medicine.high_risk,
        controlled_drug=bool(medicine.controlled_schedule),
    )
    session.add(row)
    administrations: list[MedicationAdministration] = []
    for index, scheduled_at in enumerate(times, start=1):
        administration = MedicationAdministration(
            administration_ref=f"administration-{review.review_ref}-{index}",
            order_ref=order_ref,
            episode_ref=episode_ref,
            scheduled_at=scheduled_at,
        )
        session.add(administration)
        administrations.append(administration)
    evidence_ref = record_evidence(
        session,
        entity_type="medication_order",
        entity_ref=order_ref,
        action="prescribe_from_safety_review",
        episode_ref=episode_ref,
        patient_ref=payload.patient_ref,
        previous=None,
        current={
            **row_dict(row),
            "safetyReviewRef": review.review_ref,
            "administrationRefs": [item.administration_ref for item in administrations],
            "interactionWarnings": conflicts,
        },
        reason=payload.reason,
        risk="amber" if conflicts or medicine.high_risk or medicine.controlled_schedule else "green",
        domain="medication",
    )
    for administration in administrations:
        administration.evidence_event_ref = evidence_ref
        session.add(administration)
    session.commit()
    session.refresh(row)
    return {"order": row_dict(row), "administrations": [row_dict(item) for item in administrations], "created": True, "warnings": conflicts, "evidenceEventRef": evidence_ref}


@router.patch("/anaesthesia/charts/{chart_ref}/transition")
def transition_anaesthesia_chart(
    chart_ref: str,
    payload: AnaesthesiaTransition,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*PRESCRIBER_ROLES)),
) -> dict[str, Any]:
    query = select(AnaesthesiaChartV8).where(AnaesthesiaChartV8.chart_ref == chart_ref)
    if session.get_bind().dialect.name == "postgresql":
        query = query.with_for_update()
    row = session.exec(query).first()
    if not row:
        raise HTTPException(status_code=404, detail="anaesthesia chart not found")
    if row.version != payload.expected_version:
        raise HTTPException(status_code=409, detail={"message": "stale anaesthesia chart", "currentVersion": row.version})
    transitions = {
        "planned": {"induced"},
        "induced": {"maintenance", "recovery"},
        "maintenance": {"recovery"},
        "recovery": {"completed"},
        "completed": set(),
    }
    target = normalise(payload.status)
    if target not in transitions.get(row.status, set()):
        raise HTTPException(status_code=409, detail=f"anaesthesia transition {row.status} -> {target} is not permitted")
    if target == "induced":
        checks = row.machine_check or {}
        missing = [key for key in ("machine", "patient_identity", "consent", "airway") if not checks.get(key)]
        if missing or not row.airway_plan or not row.analgesia_plan:
            raise HTTPException(status_code=409, detail={"message": "induction gates incomplete", "missing": missing + (["airway_plan"] if not row.airway_plan else []) + (["analgesia_plan"] if not row.analgesia_plan else [])})
        row.induction_at = utc_now()
    elif target == "recovery":
        row.extubation_at = utc_now()
    elif target == "completed":
        if not payload.recovery_score:
            raise HTTPException(status_code=409, detail="recovery score is required before completing anaesthesia")
        row.recovery_score = payload.recovery_score
        row.recovery_complete_at = utc_now()
    previous = row_dict(row)
    previous["status"] = row.status
    row.status = target
    row.version += 1
    row.updated_at = utc_now()
    session.add(row)
    row.evidence_event_ref = record_evidence(
        session,
        entity_type="anaesthesia_chart",
        entity_ref=chart_ref,
        action=f"transition_{target}",
        episode_ref=row.episode_ref,
        patient_ref=row.patient_ref,
        previous=previous,
        current=row_dict(row),
        reason=payload.reason,
        risk="amber",
        domain="anaesthesia",
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return {"chart": row_dict(row)}


@router.patch("/documents/{document_ref}/approve")
def approve_document(
    document_ref: str,
    payload: DocumentApprove,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*DOCUMENT_APPROVER_ROLES)),
) -> dict[str, Any]:
    query = select(ClinicalDocumentV8).where(ClinicalDocumentV8.document_ref == document_ref)
    if session.get_bind().dialect.name == "postgresql":
        query = query.with_for_update()
    row = session.exec(query).first()
    if not row:
        raise HTTPException(status_code=404, detail="clinical document not found")
    if row.version != payload.expected_version:
        raise HTTPException(status_code=409, detail={"message": "stale clinical document", "currentVersion": row.version})
    if row.status != "draft" or not row.content.strip():
        raise HTTPException(status_code=409, detail="only a non-empty draft document can be approved")
    previous = row_dict(row)
    row.status = "approved"
    row.approved_by_subject = auth.subject
    row.approved_at = utc_now()
    row.version += 1
    session.add(row)
    row.evidence_event_ref = record_evidence(
        session,
        entity_type="clinical_document",
        entity_ref=document_ref,
        action="approve",
        episode_ref=row.episode_ref,
        patient_ref=row.patient_ref,
        previous=previous,
        current={"documentRef": document_ref, "status": row.status, "version": row.version, "approvedBy": auth.subject},
        reason=payload.reason,
        risk="amber",
        domain="clinical_documentation",
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return {"document": row_dict(row)}


@router.post("/documents/{document_ref}/send")
def send_document(
    document_ref: str,
    payload: DocumentSend,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    query = select(ClinicalDocumentV8).where(ClinicalDocumentV8.document_ref == document_ref)
    if session.get_bind().dialect.name == "postgresql":
        query = query.with_for_update()
    row = session.exec(query).first()
    if not row:
        raise HTTPException(status_code=404, detail="clinical document not found")
    if row.version != payload.expected_version:
        raise HTTPException(status_code=409, detail={"message": "stale clinical document", "currentVersion": row.version})
    if row.status != "approved":
        raise HTTPException(status_code=409, detail="document must be approved before sending")
    if payload.audience not in {"owner", "referring_vet", "insurer"}:
        raise HTTPException(status_code=422, detail="unsupported document audience")
    previous = row_dict(row)
    communication = CommunicationEventV8(
        communication_ref=new_ref("communication"),
        patient_ref=row.patient_ref,
        episode_ref=row.episode_ref,
        owner_ref=payload.owner_ref,
        audience=payload.audience,
        channel=payload.channel,
        direction="outbound",
        subject=row.title,
        summary=f"Approved {row.document_type} sent to {payload.audience}",
        outcome="sent",
        attachments=[{"documentRef": row.document_ref, "recipientRef": payload.recipient_ref}],
        actor_subject=auth.subject,
    )
    session.add(communication)
    row.status = "sent"
    row.sent_at = utc_now()
    row.version += 1
    session.add(row)
    evidence_ref = record_evidence(
        session,
        entity_type="clinical_document",
        entity_ref=document_ref,
        action="send",
        episode_ref=row.episode_ref,
        patient_ref=row.patient_ref,
        previous=previous,
        current={"documentRef": document_ref, "status": row.status, "version": row.version, "audience": payload.audience, "channel": payload.channel, "recipientRef": payload.recipient_ref},
        reason=payload.reason,
        risk="green",
        domain="client_communication",
    )
    row.evidence_event_ref = evidence_ref
    communication.evidence_event_ref = evidence_ref
    session.add(row)
    session.add(communication)
    session.commit()
    session.refresh(row)
    session.refresh(communication)
    return {"document": row_dict(row), "communication": row_dict(communication)}
