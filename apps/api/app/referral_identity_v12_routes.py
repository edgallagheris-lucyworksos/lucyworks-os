from __future__ import annotations

import hashlib
import re
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.auth import AuthContext, require_authenticated, require_roles
from app.database import get_session
from app.detailed_hospital_models import OwnerAccountV8, PatientClinicalRecordV8, PatientOwnerLinkV8
from app.hospital_command_models import ReferralIntakeV9
from app.hospital_command_routes import record_evidence, row_dict
from app.hospital_ops_models import CanonicalEpisodeState, OperationalArea, OperationalBlock
from app.hospital_ops_service import block_dict, create_block, ensure_default_premises_and_areas, normalise_dt
from app.referral_identity_v12_models import (
    AccessReviewV12,
    IdentityMatchReviewV12,
    ReferralDocumentV12,
    ReferralIdentityIntakeV12,
    ReferralTriageV12,
    utc_now,
)

router = APIRouter(prefix="/api/v12", tags=["referral-identity-assurance-v12"])
INTAKE_ROLES = ("admin", "ops_manager", "clinician", "clinical_director", "senior_clinician", "supervisor", "nurse")
IDENTITY_REVIEW_ROLES = ("admin", "ops_manager", "clinical_director", "senior_clinician", "supervisor")
TRIAGE_ROLES = ("clinician", "clinical_director", "senior_clinician", "supervisor")
ACCESS_REVIEW_ROLES = ("admin", "governance_lead", "hospital_director", "clinical_director")


class DocumentInput(BaseModel):
    documentType: str = "referral_letter"
    filename: str
    mimeType: str = "application/octet-stream"
    storageRef: str
    checksumSha256: str
    sourceSystem: str = "manual_intake"


class ReferralIdentityCreate(BaseModel):
    premisesRef: str = "default-premises"
    patientName: str
    species: str
    breed: str | None = None
    sex: str | None = None
    dateOfBirth: date | None = None
    microchipNumber: str | None = None
    ownerName: str
    ownerEmail: str | None = None
    ownerPhone: str | None = None
    ownerAddress: dict[str, Any] = Field(default_factory=dict)
    decisionAuthority: bool = True
    financialResponsibility: bool = True
    sourceType: str = "referring_vet"
    sourceOrganisation: str | None = None
    sourceContactName: str | None = None
    sourceContactEmail: str | None = None
    sourceContactPhone: str | None = None
    requestedService: str
    presentingProblem: str
    clinicalSummary: str = ""
    urgency: str = "routine"
    requestedTimeframe: str | None = None
    documents: list[DocumentInput] = Field(default_factory=list)
    reason: str


class IdentityResolution(BaseModel):
    expectedVersion: int
    decision: str
    patientRef: str | None = None
    reason: str


class ReferralDecisionV12(BaseModel):
    expectedVersion: int
    status: str
    reason: str
    proposedDurationMinutes: int | None = Field(default=None, ge=15, le=720)


class TriageUpdate(BaseModel):
    expectedVersion: int
    status: str
    category: str | None = None
    score: int | None = Field(default=None, ge=0, le=100)
    rationale: str | None = None
    assignedSubject: str | None = None
    reason: str


class AccessReviewCreate(BaseModel):
    subjectRef: str
    subjectName: str
    platformRole: str
    identityGroup: str
    requestedCapabilities: list[str] = Field(default_factory=list)
    restrictedCapabilities: list[str] = Field(default_factory=list)
    dueDays: int = Field(default=30, ge=1, le=365)
    reason: str


class AccessReviewDecision(BaseModel):
    expectedVersion: int
    decision: str
    restrictedCapabilities: list[str] | None = None
    reason: str


def new_ref(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def normalise_text(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").lower())


def normalise_contact(value: str | None) -> str:
    return re.sub(r"\s+", "", (value or "").lower())


def document_checksum(value: str) -> str:
    cleaned = value.strip().lower()
    if re.fullmatch(r"[0-9a-f]{64}", cleaned):
        return cleaned
    raise HTTPException(status_code=422, detail="checksumSha256 must be a 64-character SHA-256 value")


def _owner_contacts(session: Session, patient_ref: str) -> tuple[list[str], list[str], list[str]]:
    links = session.exec(select(PatientOwnerLinkV8).where(PatientOwnerLinkV8.patient_ref == patient_ref, PatientOwnerLinkV8.active == True)).all()  # noqa: E712
    owner_refs = [row.owner_ref for row in links]
    owners = session.exec(select(OwnerAccountV8).where(OwnerAccountV8.owner_ref.in_(owner_refs))).all() if owner_refs else []
    return owner_refs, [normalise_contact(row.email) for row in owners if row.email], [normalise_contact(row.phone) for row in owners if row.phone]


def duplicate_candidates(session: Session, payload: ReferralIdentityCreate) -> list[dict[str, Any]]:
    patient_name = normalise_text(payload.patientName)
    species = normalise_text(payload.species)
    chip = normalise_text(payload.microchipNumber)
    email = normalise_contact(payload.ownerEmail)
    phone = normalise_contact(payload.ownerPhone)
    rows = session.exec(select(PatientClinicalRecordV8).where(PatientClinicalRecordV8.status == "active")).all()
    matches: list[dict[str, Any]] = []
    for row in rows:
        score = 0
        reasons: list[str] = []
        if chip and normalise_text(row.microchip_number) == chip:
            score = 100
            reasons.append("exact microchip number")
        same_name = normalise_text(row.display_name) == patient_name
        same_species = normalise_text(row.species) == species
        same_dob = bool(payload.dateOfBirth and row.date_of_birth == payload.dateOfBirth)
        if same_name and same_species and same_dob:
            score = max(score, 82)
            reasons.append("same patient name, species and date of birth")
        elif same_name and same_species:
            score = max(score, 48)
            reasons.append("same patient name and species")
        owner_refs, emails, phones = _owner_contacts(session, row.patient_ref)
        contact_match = bool((email and email in emails) or (phone and phone in phones))
        if contact_match:
            score += 22
            reasons.append("owner contact matches an active patient-owner link")
        if score >= 45:
            matches.append({
                "patientRef": row.patient_ref,
                "patientName": row.display_name,
                "species": row.species,
                "breed": row.breed,
                "dateOfBirth": row.date_of_birth.isoformat() if row.date_of_birth else None,
                "microchipNumber": row.microchip_number,
                "ownerRefs": owner_refs,
                "score": min(score, 100),
                "reasons": reasons,
            })
    return sorted(matches, key=lambda item: (-item["score"], item["patientName"]))[:8]


def _find_or_create_owner(session: Session, intake: ReferralIdentityIntakeV12, auth: AuthContext) -> OwnerAccountV8:
    owner = None
    if intake.owner_email:
        owner = session.exec(select(OwnerAccountV8).where(OwnerAccountV8.email == intake.owner_email)).first()
    if not owner and intake.owner_phone:
        owner = session.exec(select(OwnerAccountV8).where(OwnerAccountV8.phone == intake.owner_phone)).first()
    if owner:
        return owner
    owner = OwnerAccountV8(
        owner_ref=new_ref("owner"),
        display_name=intake.owner_name,
        email=intake.owner_email,
        phone=intake.owner_phone,
        address=intake.owner_address,
        communication_preferences={},
        identity_verified=False,
    )
    session.add(owner)
    session.flush()
    owner.evidence_event_ref = record_evidence(
        session, entity_type="owner_identity", entity_ref=owner.owner_ref, action="created_from_referral_intake",
        episode_ref=None, patient_ref=None, previous=None, current=row_dict(owner),
        reason="Owner identity created from governed referral intake", risk="amber",
    )
    session.add(owner)
    return owner


def _create_patient(session: Session, intake: ReferralIdentityIntakeV12, auth: AuthContext) -> PatientClinicalRecordV8:
    dob = date.fromisoformat(intake.date_of_birth_text) if intake.date_of_birth_text else None
    patient = PatientClinicalRecordV8(
        patient_ref=new_ref("patient"),
        display_name=intake.patient_name,
        species=intake.species,
        breed=intake.breed,
        sex=intake.sex,
        date_of_birth=dob,
        microchip_number=intake.microchip_number,
        alerts=[],
    )
    session.add(patient)
    session.flush()
    patient.evidence_event_ref = record_evidence(
        session, entity_type="patient_identity", entity_ref=patient.patient_ref, action="created_from_referral_intake",
        episode_ref=None, patient_ref=patient.patient_ref, previous=None, current=row_dict(patient),
        reason="Patient identity created after duplicate screening", risk="amber",
    )
    session.add(patient)
    return patient


def _ensure_owner_link(session: Session, intake: ReferralIdentityIntakeV12, patient: PatientClinicalRecordV8, owner: OwnerAccountV8) -> PatientOwnerLinkV8:
    link = session.exec(select(PatientOwnerLinkV8).where(
        PatientOwnerLinkV8.patient_ref == patient.patient_ref,
        PatientOwnerLinkV8.owner_ref == owner.owner_ref,
        PatientOwnerLinkV8.active == True,  # noqa: E712
    )).first()
    if link:
        return link
    link = PatientOwnerLinkV8(
        link_ref=new_ref("owner-link"),
        patient_ref=patient.patient_ref,
        owner_ref=owner.owner_ref,
        relationship="registered_owner",
        decision_authority=intake.decision_authority_claimed,
        financial_responsibility=intake.financial_responsibility_claimed,
    )
    session.add(link)
    session.flush()
    link.evidence_event_ref = record_evidence(
        session, entity_type="patient_owner_authority", entity_ref=link.link_ref, action="linked_from_referral_intake",
        episode_ref=None, patient_ref=patient.patient_ref, previous=None, current=row_dict(link),
        reason="Owner relationship and claimed authority recorded at referral intake", risk="amber",
    )
    session.add(link)
    return link


def _triage_values(urgency: str, problem: str, summary: str) -> tuple[str, int, int, int, list[str]]:
    text = f"{problem} {summary}".lower()
    red_terms = ["collapse", "respiratory distress", "uncontrolled bleeding", "status epilepticus", "cardiac arrest", "gdv"]
    urgent_terms = ["paralysis", "unable to urinate", "seizure", "acute abdomen", "severe pain", "dyspnoea"]
    red_flags = [term for term in red_terms + urgent_terms if term in text]
    normal = urgency.lower()
    if normal in {"red", "emergency"} or any(term in text for term in red_terms):
        return "emergency", 100, 10, 15, red_flags
    if normal == "urgent" or red_flags:
        return "urgent", 70, 60, 120, red_flags
    return "routine", 30, 240, 1440, red_flags


def _create_referral_package(
    session: Session,
    intake: ReferralIdentityIntakeV12,
    patient: PatientClinicalRecordV8,
    owner: OwnerAccountV8,
    auth: AuthContext,
) -> tuple[ReferralIntakeV9, CanonicalEpisodeState, ReferralTriageV12, list[ReferralDocumentV12]]:
    payload = intake.referral_payload
    referral_ref = new_ref("referral")
    episode_ref = new_ref("episode")
    referral = ReferralIntakeV9(
        referral_ref=referral_ref,
        episode_ref=episode_ref,
        patient_ref=patient.patient_ref,
        premises_ref=intake.premises_ref,
        source_type=payload.get("sourceType") or "referring_vet",
        source_organisation=payload.get("sourceOrganisation"),
        source_contact_name=payload.get("sourceContactName"),
        source_contact_email=payload.get("sourceContactEmail"),
        source_contact_phone=payload.get("sourceContactPhone"),
        requested_service=payload.get("requestedService") or "referral",
        presenting_problem=payload.get("presentingProblem") or "",
        clinical_summary=payload.get("clinicalSummary") or "",
        urgency=payload.get("urgency") or "routine",
        requested_timeframe=payload.get("requestedTimeframe"),
        attachments=[],
        created_by_subject=auth.subject,
    )
    episode = CanonicalEpisodeState(
        episode_ref=episode_ref,
        patient_ref=patient.patient_ref,
        patient_name=patient.display_name,
        premises_ref=intake.premises_ref,
        service_line=referral.requested_service,
        urgency=referral.urgency,
        phase="referral_received",
        status="active",
        owner_role="admin",
        owner_subject=auth.subject,
        next_action="Complete triage and clinical referral decision",
    )
    session.add(referral)
    session.add(episode)
    session.flush()

    category, score, response_minutes, review_minutes, flags = _triage_values(
        referral.urgency, referral.presenting_problem, referral.clinical_summary
    )
    now = utc_now()
    triage = ReferralTriageV12(
        triage_ref=new_ref("triage"),
        referral_ref=referral_ref,
        episode_ref=episode_ref,
        patient_ref=patient.patient_ref,
        category=category,
        score=score,
        rationale=f"{referral.urgency} referral; automated intake classification pending clinician confirmation",
        red_flags=flags,
        response_due_at=now + timedelta(minutes=response_minutes),
        clinical_review_due_at=now + timedelta(minutes=review_minutes),
        assigned_role="clinician",
        status="pending",
    )
    session.add(triage)
    session.flush()

    documents: list[ReferralDocumentV12] = []
    for item in payload.get("documents") or []:
        document = ReferralDocumentV12(
            document_ref=new_ref("referral-document"),
            intake_ref=intake.intake_ref,
            referral_ref=referral_ref,
            episode_ref=episode_ref,
            patient_ref=patient.patient_ref,
            document_type=item.get("documentType") or "referral_letter",
            filename=item["filename"],
            mime_type=item.get("mimeType") or "application/octet-stream",
            storage_ref=item["storageRef"],
            checksum_sha256=document_checksum(item["checksumSha256"]),
            source_system=item.get("sourceSystem") or "manual_intake",
            created_by_subject=auth.subject,
        )
        session.add(document)
        documents.append(document)
    session.flush()

    referral.evidence_event_ref = record_evidence(
        session, entity_type="referral", entity_ref=referral_ref, action="received_v12",
        episode_ref=episode_ref, patient_ref=patient.patient_ref, previous=None, current=row_dict(referral),
        reason=intake.resolution_reason or "Referral package created from governed identity intake",
        risk="red" if category == "emergency" else "amber",
    )
    triage.evidence_event_ref = record_evidence(
        session, entity_type="referral_triage", entity_ref=triage.triage_ref, action="created",
        episode_ref=episode_ref, patient_ref=patient.patient_ref, previous=None, current=row_dict(triage),
        reason="Response and clinical-review SLA generated from recorded referral urgency and red flags",
        risk="red" if category == "emergency" else "amber",
    )
    for document in documents:
        document.evidence_event_ref = record_evidence(
            session, entity_type="referral_document", entity_ref=document.document_ref, action="provenance_recorded",
            episode_ref=episode_ref, patient_ref=patient.patient_ref, previous=None, current=row_dict(document),
            reason="Referral document metadata, source and checksum recorded", risk="green",
        )
        session.add(document)
    session.add(referral)
    session.add(triage)

    intake.status = "created"
    intake.patient_ref = patient.patient_ref
    intake.owner_ref = owner.owner_ref
    intake.referral_ref = referral_ref
    intake.episode_ref = episode_ref
    intake.resolved_by_subject = auth.subject
    intake.updated_at = utc_now()
    intake.version += 1
    intake.evidence_event_ref = record_evidence(
        session, entity_type="referral_identity_intake", entity_ref=intake.intake_ref, action="resolved",
        episode_ref=episode_ref, patient_ref=patient.patient_ref, previous=None, current=row_dict(intake),
        reason=intake.resolution_reason or "Identity intake resolved and canonical referral created", risk="amber",
    )
    session.add(intake)
    return referral, episode, triage, documents


def _intake_response(session: Session, intake: ReferralIdentityIntakeV12) -> dict[str, Any]:
    reviews = session.exec(select(IdentityMatchReviewV12).where(IdentityMatchReviewV12.intake_ref == intake.intake_ref).order_by(IdentityMatchReviewV12.match_score.desc())).all()
    return {
        "intake": row_dict(intake),
        "identityReviews": [row_dict(row) for row in reviews],
        "requiresIdentityReview": intake.status == "duplicate_review",
    }


@router.post("/referrals/intake")
def create_identity_intake(
    payload: ReferralIdentityCreate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*INTAKE_ROLES)),
) -> dict[str, Any]:
    if not payload.patientName.strip() or not payload.species.strip() or not payload.ownerName.strip():
        raise HTTPException(status_code=422, detail="patientName, species and ownerName are required")
    if not payload.requestedService.strip() or not payload.presentingProblem.strip():
        raise HTTPException(status_code=422, detail="requestedService and presentingProblem are required")
    for item in payload.documents:
        document_checksum(item.checksumSha256)
    intake = ReferralIdentityIntakeV12(
        intake_ref=new_ref("identity-intake"),
        premises_ref=payload.premisesRef,
        patient_name=payload.patientName.strip(),
        species=payload.species.strip(),
        breed=payload.breed,
        sex=payload.sex,
        date_of_birth_text=payload.dateOfBirth.isoformat() if payload.dateOfBirth else None,
        microchip_number=payload.microchipNumber,
        owner_name=payload.ownerName.strip(),
        owner_email=payload.ownerEmail,
        owner_phone=payload.ownerPhone,
        owner_address=payload.ownerAddress,
        decision_authority_claimed=payload.decisionAuthority,
        financial_responsibility_claimed=payload.financialResponsibility,
        referral_payload=payload.model_dump(mode="json", exclude={"patientName", "species", "breed", "sex", "dateOfBirth", "microchipNumber", "ownerName", "ownerEmail", "ownerPhone", "ownerAddress", "decisionAuthority", "financialResponsibility", "premisesRef", "reason"}),
        created_by_subject=auth.subject,
        resolution_reason=payload.reason,
    )
    session.add(intake)
    session.flush()
    matches = duplicate_candidates(session, payload)
    intake.duplicate_count = len(matches)
    if matches:
        intake.status = "duplicate_review"
        for item in matches:
            session.add(IdentityMatchReviewV12(
                review_ref=new_ref("identity-review"),
                intake_ref=intake.intake_ref,
                candidate_patient_ref=item["patientRef"],
                candidate_owner_refs=item["ownerRefs"],
                match_score=item["score"],
                reasons=item["reasons"],
            ))
        intake.evidence_event_ref = record_evidence(
            session, entity_type="referral_identity_intake", entity_ref=intake.intake_ref, action="duplicate_review_required",
            episode_ref=None, patient_ref=None, previous=None, current={"intake": row_dict(intake), "matches": matches},
            reason="Potential duplicate patient identity detected; referral creation held for review", risk="red",
        )
        session.add(intake)
        session.commit()
        session.refresh(intake)
        return _intake_response(session, intake)

    owner = _find_or_create_owner(session, intake, auth)
    patient = _create_patient(session, intake, auth)
    _ensure_owner_link(session, intake, patient, owner)
    referral, episode, triage, documents = _create_referral_package(session, intake, patient, owner, auth)
    session.commit()
    return {
        **_intake_response(session, intake),
        "owner": row_dict(owner),
        "patient": row_dict(patient),
        "referral": row_dict(referral),
        "episode": row_dict(episode),
        "triage": row_dict(triage),
        "documents": [row_dict(row) for row in documents],
    }


@router.get("/identity-intakes")
def list_identity_intakes(
    status: str | None = None,
    limit: int = Query(default=100, ge=1, le=300),
    session: Session = Depends(get_session),
    _: AuthContext = Depends(require_roles(*INTAKE_ROLES)),
) -> dict[str, Any]:
    query = select(ReferralIdentityIntakeV12).order_by(ReferralIdentityIntakeV12.created_at.desc())
    if status:
        query = query.where(ReferralIdentityIntakeV12.status == status)
    rows = session.exec(query.limit(limit)).all()
    return {"items": [_intake_response(session, row) for row in rows], "count": len(rows)}


@router.post("/identity-intakes/{intake_ref}/resolve")
def resolve_identity_intake(
    intake_ref: str,
    payload: IdentityResolution,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*IDENTITY_REVIEW_ROLES)),
) -> dict[str, Any]:
    query = select(ReferralIdentityIntakeV12).where(ReferralIdentityIntakeV12.intake_ref == intake_ref)
    if session.get_bind().dialect.name == "postgresql":
        query = query.with_for_update()
    intake = session.exec(query).first()
    if not intake:
        raise HTTPException(status_code=404, detail="identity intake not found")
    if intake.version != payload.expectedVersion:
        raise HTTPException(status_code=409, detail={"message": "stale identity intake", "currentVersion": intake.version})
    if intake.status != "duplicate_review":
        raise HTTPException(status_code=409, detail="identity intake is not awaiting duplicate review")
    if payload.decision not in {"link_existing", "create_new"}:
        raise HTTPException(status_code=422, detail="decision must be link_existing or create_new")
    intake.resolution_reason = payload.reason
    owner = _find_or_create_owner(session, intake, auth)
    if payload.decision == "link_existing":
        if not payload.patientRef:
            raise HTTPException(status_code=422, detail="patientRef is required when linking an existing patient")
        patient = session.exec(select(PatientClinicalRecordV8).where(PatientClinicalRecordV8.patient_ref == payload.patientRef)).first()
        if not patient:
            raise HTTPException(status_code=404, detail="selected patient identity not found")
    else:
        patient = _create_patient(session, intake, auth)
    _ensure_owner_link(session, intake, patient, owner)
    reviews = session.exec(select(IdentityMatchReviewV12).where(IdentityMatchReviewV12.intake_ref == intake_ref)).all()
    for review in reviews:
        review.status = "decided"
        review.decision = "selected" if review.candidate_patient_ref == patient.patient_ref else "not_selected"
        review.decided_by_subject = auth.subject
        review.decided_at = utc_now()
        review.version += 1
        review.evidence_event_ref = record_evidence(
            session, entity_type="identity_match_review", entity_ref=review.review_ref, action=review.decision,
            episode_ref=None, patient_ref=review.candidate_patient_ref, previous=None, current=row_dict(review),
            reason=payload.reason, risk="amber",
        )
        session.add(review)
    referral, episode, triage, documents = _create_referral_package(session, intake, patient, owner, auth)
    session.commit()
    return {
        **_intake_response(session, intake),
        "owner": row_dict(owner),
        "patient": row_dict(patient),
        "referral": row_dict(referral),
        "episode": row_dict(episode),
        "triage": row_dict(triage),
        "documents": [row_dict(row) for row in documents],
    }


@router.get("/triage")
def triage_queue(
    status: str | None = None,
    category: str | None = None,
    limit: int = Query(default=100, ge=1, le=300),
    session: Session = Depends(get_session),
    _: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    query = select(ReferralTriageV12).order_by(ReferralTriageV12.response_due_at)
    if status:
        query = query.where(ReferralTriageV12.status == status)
    if category:
        query = query.where(ReferralTriageV12.category == category)
    rows = session.exec(query.limit(limit)).all()
    now = utc_now()
    items = []
    for row in rows:
        item = row_dict(row)
        item["responseOverdue"] = row.status == "pending" and row.response_due_at < now
        item["clinicalReviewOverdue"] = row.status not in {"completed", "closed"} and row.clinical_review_due_at < now
        items.append(item)
    return {"items": items, "count": len(items), "generatedAt": now.isoformat()}


@router.patch("/triage/{triage_ref}")
def update_triage(
    triage_ref: str,
    payload: TriageUpdate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*TRIAGE_ROLES)),
) -> dict[str, Any]:
    query = select(ReferralTriageV12).where(ReferralTriageV12.triage_ref == triage_ref)
    if session.get_bind().dialect.name == "postgresql":
        query = query.with_for_update()
    row = session.exec(query).first()
    if not row:
        raise HTTPException(status_code=404, detail="triage record not found")
    if row.version != payload.expectedVersion:
        raise HTTPException(status_code=409, detail={"message": "stale triage record", "currentVersion": row.version})
    if payload.status not in {"pending", "acknowledged", "completed", "escalated"}:
        raise HTTPException(status_code=422, detail="unsupported triage status")
    before = row_dict(row)
    row.status = payload.status
    if payload.category:
        row.category = payload.category
    if payload.score is not None:
        row.score = payload.score
    if payload.rationale:
        row.rationale = payload.rationale
    if payload.assignedSubject is not None:
        row.assigned_subject = payload.assignedSubject
    if payload.status == "acknowledged" and not row.acknowledged_at:
        row.acknowledged_at = utc_now()
    if payload.status == "completed":
        row.completed_at = utc_now()
    row.version += 1
    row.updated_at = utc_now()
    row.evidence_event_ref = record_evidence(
        session, entity_type="referral_triage", entity_ref=row.triage_ref, action=payload.status,
        episode_ref=row.episode_ref, patient_ref=row.patient_ref, previous=before, current=row_dict(row),
        reason=payload.reason, risk="red" if row.category == "emergency" else "amber",
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return {"triage": row_dict(row)}


def _service_area(session: Session, premises_ref: str, requested_service: str) -> OperationalArea:
    _, areas = ensure_default_premises_and_areas(session, premises_ref)
    service = requested_service.lower()
    preferred = "consult-1"
    for token, area_ref in (
        ("mri", "mri"), ("ct", "ct"), ("radiograph", "xray"), ("x-ray", "xray"),
        ("ultrasound", "ultrasound"), ("surgery", "theatre-1"), ("theatre", "theatre-1"),
        ("orthopaedic", "theatre-1"),
    ):
        if token in service:
            preferred = area_ref
            break
    area = next((row for row in areas if row.area_ref == preferred), None)
    if not area:
        raise HTTPException(status_code=409, detail="no compatible operational area is configured")
    return area


def _next_slot(session: Session, premises_ref: str, area: OperationalArea, duration_minutes: int) -> datetime:
    now = utc_now() + timedelta(minutes=30)
    minute = ((now.minute + 14) // 15) * 15
    start = now.replace(second=0, microsecond=0)
    if minute == 60:
        start = start.replace(minute=0) + timedelta(hours=1)
    else:
        start = start.replace(minute=minute)
    for offset in range(0, 14):
        day = (start + timedelta(days=offset)).date()
        cursor = datetime.combine(day, time(8, 0), tzinfo=timezone.utc)
        if day == start.date() and start > cursor:
            cursor = start
        end_of_day = datetime.combine(day, time(18, 0), tzinfo=timezone.utc)
        rows = session.exec(select(OperationalBlock).where(
            OperationalBlock.premises_ref == premises_ref,
            OperationalBlock.area_ref == area.area_ref,
            OperationalBlock.operational_date == day,
            OperationalBlock.status.notin_(["cancelled", "completed"]),
        ).order_by(OperationalBlock.starts_at)).all()
        while cursor + timedelta(minutes=duration_minutes) <= end_of_day:
            proposed_end = cursor + timedelta(minutes=duration_minutes + area.turnover_minutes)
            if not any(normalise_dt(row.starts_at) < proposed_end and cursor < normalise_dt(row.ends_at) for row in rows):
                return cursor
            cursor += timedelta(minutes=15)
    raise HTTPException(status_code=409, detail="no operational slot is available within the next 14 days")


def _propose_operational_block(
    session: Session,
    referral: ReferralIntakeV9,
    episode: CanonicalEpisodeState,
    duration_minutes: int | None,
    auth: AuthContext,
) -> OperationalBlock:
    existing = session.exec(select(OperationalBlock).where(
        OperationalBlock.episode_ref == referral.episode_ref,
        OperationalBlock.status.notin_(["cancelled"]),
    ).order_by(OperationalBlock.created_at)).first()
    if existing:
        return existing
    area = _service_area(session, referral.premises_ref, referral.requested_service)
    duration = duration_minutes or (90 if area.area_type in {"theatre", "imaging"} else 60)
    starts_at = _next_slot(session, referral.premises_ref, area, duration)
    category, _, _, _, _ = _triage_values(referral.urgency, referral.presenting_problem, referral.clinical_summary)
    row, _, _ = create_block(
        session,
        {
            "premisesRef": referral.premises_ref,
            "episodeRef": referral.episode_ref,
            "patientRef": referral.patient_ref,
            "patientName": episode.patient_name,
            "procedureName": f"Proposed {referral.requested_service}",
            "blockType": "proposed_referral",
            "areaRef": area.area_ref,
            "startsAt": starts_at,
            "endsAt": starts_at + timedelta(minutes=duration),
            "status": "proposed",
            "riskLevel": "red" if category == "emergency" else "amber",
            "priority": 100 if category == "emergency" else 75 if category == "urgent" else 50,
            "gates": {"referral": "accepted", "triage": "recorded", "consent": "pending", "estimate": "pending"},
            "notes": "Created automatically from accepted governed referral; clinical plan, consent and estimate remain required",
            "reason": "Accepted referral converted to a proposed operational block",
            "idempotencyKey": f"v12:accepted-referral:{referral.referral_ref}",
        },
        auth,
    )
    return row


@router.patch("/referrals/{referral_ref}/decision")
def decide_referral_v12(
    referral_ref: str,
    payload: ReferralDecisionV12,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*TRIAGE_ROLES)),
) -> dict[str, Any]:
    query = select(ReferralIntakeV9).where(ReferralIntakeV9.referral_ref == referral_ref)
    if session.get_bind().dialect.name == "postgresql":
        query = query.with_for_update()
    referral = session.exec(query).first()
    if not referral:
        raise HTTPException(status_code=404, detail="referral not found")
    if referral.version != payload.expectedVersion:
        raise HTTPException(status_code=409, detail={"message": "stale referral", "currentVersion": referral.version})
    if payload.status not in {"accepted", "declined", "needs_information"}:
        raise HTTPException(status_code=422, detail="unsupported referral status")
    episode = session.exec(select(CanonicalEpisodeState).where(CanonicalEpisodeState.episode_ref == referral.episode_ref)).first()
    if not episode:
        raise HTTPException(status_code=409, detail="canonical episode is missing")
    before = row_dict(referral)
    referral.status = payload.status
    referral.acceptance_reason = payload.reason
    referral.accepted_by_subject = auth.subject
    referral.accepted_at = utc_now() if payload.status == "accepted" else None
    referral.version += 1
    referral.updated_at = utc_now()
    referral.evidence_event_ref = record_evidence(
        session, entity_type="referral", entity_ref=referral.referral_ref, action=payload.status,
        episode_ref=referral.episode_ref, patient_ref=referral.patient_ref, previous=before, current=row_dict(referral),
        reason=payload.reason, risk="amber",
    )
    session.add(referral)
    proposed = None
    if payload.status == "accepted":
        proposed = _propose_operational_block(session, referral, episode, payload.proposedDurationMinutes, auth)
        episode.owner_role = "ops_manager"
        episode.owner_subject = auth.subject
        episode.next_action = "Review and confirm proposed operational block; complete consent and estimate gates"
        episode.version += 1
        episode.updated_at = utc_now()
        session.add(episode)
        triage = session.exec(select(ReferralTriageV12).where(ReferralTriageV12.referral_ref == referral.referral_ref)).first()
        if triage and triage.status != "completed":
            triage.status = "completed"
            triage.completed_at = utc_now()
            triage.version += 1
            triage.updated_at = utc_now()
            session.add(triage)
    session.commit()
    return {
        "referral": row_dict(referral),
        "episode": row_dict(episode),
        "proposedBlock": block_dict(proposed) if proposed else None,
    }


@router.post("/referrals/{referral_ref}/documents")
def add_referral_document(
    referral_ref: str,
    payload: DocumentInput,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*INTAKE_ROLES)),
) -> dict[str, Any]:
    referral = session.exec(select(ReferralIntakeV9).where(ReferralIntakeV9.referral_ref == referral_ref)).first()
    if not referral:
        raise HTTPException(status_code=404, detail="referral not found")
    row = ReferralDocumentV12(
        document_ref=new_ref("referral-document"),
        referral_ref=referral.referral_ref,
        episode_ref=referral.episode_ref,
        patient_ref=referral.patient_ref,
        document_type=payload.documentType,
        filename=payload.filename,
        mime_type=payload.mimeType,
        storage_ref=payload.storageRef,
        checksum_sha256=document_checksum(payload.checksumSha256),
        source_system=payload.sourceSystem,
        created_by_subject=auth.subject,
    )
    session.add(row)
    session.flush()
    row.evidence_event_ref = record_evidence(
        session, entity_type="referral_document", entity_ref=row.document_ref, action="provenance_recorded",
        episode_ref=row.episode_ref, patient_ref=row.patient_ref, previous=None, current=row_dict(row),
        reason="Additional referral document metadata and checksum recorded", risk="green",
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return {"document": row_dict(row)}


@router.get("/referrals/{referral_ref}/documents")
def list_referral_documents(
    referral_ref: str,
    session: Session = Depends(get_session),
    _: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    rows = session.exec(select(ReferralDocumentV12).where(ReferralDocumentV12.referral_ref == referral_ref).order_by(ReferralDocumentV12.received_at.desc())).all()
    return {"documents": [row_dict(row) for row in rows], "count": len(rows)}


@router.post("/access-reviews")
def create_access_review(
    payload: AccessReviewCreate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*ACCESS_REVIEW_ROLES)),
) -> dict[str, Any]:
    row = AccessReviewV12(
        review_ref=new_ref("access-review"),
        subject_ref=payload.subjectRef,
        subject_name=payload.subjectName,
        platform_role=payload.platformRole,
        identity_group=payload.identityGroup,
        requested_capabilities=payload.requestedCapabilities,
        restricted_capabilities=payload.restrictedCapabilities,
        reason=payload.reason,
        due_at=utc_now() + timedelta(days=payload.dueDays),
        created_by_subject=auth.subject,
    )
    session.add(row)
    session.flush()
    row.evidence_event_ref = record_evidence(
        session, entity_type="access_review", entity_ref=row.review_ref, action="opened",
        episode_ref=None, patient_ref=None, previous=None, current=row_dict(row),
        reason=payload.reason, risk="amber",
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return {"accessReview": row_dict(row)}


@router.get("/access-reviews")
def list_access_reviews(
    status: str | None = None,
    subject_ref: str | None = None,
    session: Session = Depends(get_session),
    _: AuthContext = Depends(require_roles(*ACCESS_REVIEW_ROLES)),
) -> dict[str, Any]:
    query = select(AccessReviewV12).order_by(AccessReviewV12.due_at)
    if status:
        query = query.where(AccessReviewV12.status == status)
    if subject_ref:
        query = query.where(AccessReviewV12.subject_ref == subject_ref)
    rows = session.exec(query).all()
    now = utc_now()
    items = []
    for row in rows:
        item = row_dict(row)
        item["overdue"] = row.status == "pending" and row.due_at < now
        items.append(item)
    return {"items": items, "count": len(items)}


@router.patch("/access-reviews/{review_ref}")
def decide_access_review(
    review_ref: str,
    payload: AccessReviewDecision,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*ACCESS_REVIEW_ROLES)),
) -> dict[str, Any]:
    query = select(AccessReviewV12).where(AccessReviewV12.review_ref == review_ref)
    if session.get_bind().dialect.name == "postgresql":
        query = query.with_for_update()
    row = session.exec(query).first()
    if not row:
        raise HTTPException(status_code=404, detail="access review not found")
    if row.version != payload.expectedVersion:
        raise HTTPException(status_code=409, detail={"message": "stale access review", "currentVersion": row.version})
    if payload.decision not in {"approved", "restricted", "revoked", "changes_required"}:
        raise HTTPException(status_code=422, detail="unsupported access-review decision")
    before = row_dict(row)
    row.decision = payload.decision
    row.status = "completed" if payload.decision in {"approved", "restricted", "revoked"} else "pending"
    if payload.restrictedCapabilities is not None:
        row.restricted_capabilities = payload.restrictedCapabilities
    row.reviewer_subject = auth.subject
    row.reviewer_role = auth.role
    row.decided_at = utc_now()
    row.reason = payload.reason
    row.version += 1
    row.updated_at = utc_now()
    row.evidence_event_ref = record_evidence(
        session, entity_type="access_review", entity_ref=row.review_ref, action=payload.decision,
        episode_ref=None, patient_ref=None, previous=before, current=row_dict(row),
        reason=payload.reason, risk="red" if payload.decision == "revoked" else "amber",
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return {"accessReview": row_dict(row)}
