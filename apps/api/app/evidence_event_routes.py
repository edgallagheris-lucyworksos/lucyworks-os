from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session, select

from app.database import get_session
from app.evidence_approval_models import ApprovalTask
from app.evidence_event_models import ConsentRecord, EstimateVersion, EvidenceEvent
from app.evidence_service import (
    canonical_json,
    create_evidence_event,
    json_text,
    parse_json,
    verify_event_chain,
)

router = APIRouter(prefix="/api/evidence", tags=["evidence-events"])


class EvidenceEventCreate(BaseModel):
    eventType: str
    patientCaseId: str | None = None
    referralEpisodeId: str | None = None
    scheduleBlockId: str | None = None
    actorId: str | None = None
    actorName: str = "frontend"
    actorRole: str = "user"
    actorAuthSource: str = "payload_unverified"
    professionalRole: str | None = None
    action: str
    previousState: dict[str, Any] | list[Any] | None = None
    newState: dict[str, Any] | list[Any] | None = None
    reason: str | None = None
    justification: str | None = None
    evidenceLinks: list[dict[str, Any]] | None = None
    alternativesDiscussed: list[dict[str, Any]] | None = None
    clientAuthorisation: dict[str, Any] | None = None
    aiSystem: str | None = None
    aiModel: str | None = None
    aiPromptRef: str | None = None
    aiOutputRef: str | None = None
    aiConfidence: str | None = None
    humanReviewer: str | None = None
    humanReviewStatus: str = "not_required"
    supervisorRequired: bool = False
    supervisorName: str | None = None
    supervisorApprovalStatus: str = "not_required"
    overrideReason: str | None = None
    complianceDomain: str = "operations"
    riskLevel: str = "amber"
    sourceModule: str = "lucyworks"
    sourceSystem: str = "lucyworks-os"
    sourceRecordRef: str | None = None
    correlationId: str | None = None
    causationEventRef: str | None = None
    idempotencyKey: str | None = None
    requestId: str | None = None
    entityType: str | None = None
    entityId: str | None = None
    occurredAt: datetime | None = None


class EstimateVersionCreate(BaseModel):
    estimateRef: str
    patientCaseId: str
    referralEpisodeId: str | None = None
    idempotencyKey: str | None = None
    status: str = "draft"
    lowerAmount: float | None = None
    upperAmount: float | None = None
    approvedCeiling: float | None = None
    currency: str = "GBP"
    assumptions: list[str] | dict[str, Any] | None = None
    itemisedLines: list[dict[str, Any]] | None = None
    excludedItems: list[str] | None = None
    insuranceAssumptions: dict[str, Any] | None = None
    alternatives: list[dict[str, Any]] | None = None
    changeReason: str | None = None
    clientContactMethod: str | None = None
    clientContactAttemptedAt: datetime | None = None
    clientDecision: str = "not_recorded"
    emergencyAuthority: bool = False
    clinicianJustification: str | None = None
    createdBy: str = "frontend"
    createdByRole: str = "admin_or_clinician"


class ConsentRecordCreate(BaseModel):
    consentRef: str
    patientCaseId: str
    referralEpisodeId: str | None = None
    idempotencyKey: str | None = None
    supersedesConsentRef: str | None = None
    consentType: str = "procedure"
    status: str = "pending"
    scope: str = "not_recorded"
    risksDiscussed: list[str] | None = None
    alternativesDiscussed: list[str] | None = None
    costDiscussed: bool = False
    estimateRef: str | None = None
    clientAuthorisedBy: str | None = None
    clientContactMethod: str | None = None
    communicationNotes: str | None = None
    recordedBy: str = "frontend"
    recordedByRole: str = "admin_or_clinician"
    witness: str | None = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _request_fingerprint(prefix: str, value: Any) -> str:
    digest = hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()
    return f"{prefix}:{digest}"


def _event_dict(row: EvidenceEvent, approval: ApprovalTask | None = None) -> dict[str, Any]:
    return {
        "id": row.id,
        "eventRef": row.event_ref,
        "eventType": row.event_type,
        "correlationId": row.correlation_id,
        "causationEventRef": row.causation_event_ref,
        "idempotencyKey": row.idempotency_key,
        "requestId": row.request_id,
        "entityType": row.entity_type,
        "entityId": row.entity_id,
        "patientCaseId": row.patient_case_id,
        "referralEpisodeId": row.referral_episode_id,
        "scheduleBlockId": row.schedule_block_id,
        "actorId": row.actor_id,
        "actorName": row.actor_name,
        "actorRole": row.actor_role,
        "actorAuthSource": row.actor_auth_source,
        "professionalRole": row.professional_role,
        "action": row.action,
        "previousState": parse_json(row.previous_state_json),
        "newState": parse_json(row.new_state_json),
        "reason": row.reason,
        "justification": row.justification,
        "evidenceLinks": parse_json(row.evidence_links_json),
        "alternativesDiscussed": parse_json(row.alternatives_discussed_json),
        "clientAuthorisation": parse_json(row.client_authorisation_json),
        "aiSystem": row.ai_system,
        "aiModel": row.ai_model,
        "aiPromptRef": row.ai_prompt_ref,
        "aiOutputRef": row.ai_output_ref,
        "aiConfidence": row.ai_confidence,
        "humanReviewer": row.human_reviewer,
        "humanReviewStatus": row.human_review_status,
        "humanReviewCompletedAt": row.human_review_completed_at.isoformat() if row.human_review_completed_at else None,
        "supervisorRequired": row.supervisor_required,
        "supervisorName": row.supervisor_name,
        "supervisorApprovalStatus": row.supervisor_approval_status,
        "effectiveApprovalStatus": approval.status if approval else row.supervisor_approval_status,
        "approvalTaskId": approval.id if approval else None,
        "overrideReason": row.override_reason,
        "complianceDomain": row.compliance_domain,
        "riskLevel": row.risk_level,
        "sourceModule": row.source_module,
        "sourceSystem": row.source_system,
        "sourceRecordRef": row.source_record_ref,
        "payloadSchemaVersion": row.payload_schema_version,
        "previousEventHash": row.previous_event_hash,
        "eventHash": row.event_hash,
        "immutable": row.immutable,
        "occurredAt": row.occurred_at.isoformat() if row.occurred_at else None,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
    }


def _estimate_dict(row: EstimateVersion) -> dict[str, Any]:
    return {
        "id": row.id,
        "estimateRef": row.estimate_ref,
        "patientCaseId": row.patient_case_id,
        "referralEpisodeId": row.referral_episode_id,
        "version": row.version,
        "supersedesVersion": row.supersedes_version,
        "idempotencyKey": row.idempotency_key,
        "status": row.status,
        "lowerAmount": row.lower_amount,
        "upperAmount": row.upper_amount,
        "approvedCeiling": row.approved_ceiling,
        "currency": row.currency,
        "assumptions": parse_json(row.assumptions_json),
        "itemisedLines": parse_json(row.itemised_lines_json),
        "excludedItems": parse_json(row.excluded_items_json),
        "insuranceAssumptions": parse_json(row.insurance_assumptions_json),
        "alternatives": parse_json(row.alternatives_json),
        "changeReason": row.change_reason,
        "clientContactMethod": row.client_contact_method,
        "clientContactAttemptedAt": row.client_contact_attempted_at.isoformat() if row.client_contact_attempted_at else None,
        "clientNotifiedAt": row.client_notified_at.isoformat() if row.client_notified_at else None,
        "clientDecision": row.client_decision,
        "emergencyAuthority": row.emergency_authority,
        "clinicianJustification": row.clinician_justification,
        "createdBy": row.created_by,
        "evidenceEventRef": row.evidence_event_ref,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
    }


def _consent_dict(row: ConsentRecord) -> dict[str, Any]:
    return {
        "id": row.id,
        "consentRef": row.consent_ref,
        "patientCaseId": row.patient_case_id,
        "referralEpisodeId": row.referral_episode_id,
        "version": row.version,
        "supersedesConsentRef": row.supersedes_consent_ref,
        "idempotencyKey": row.idempotency_key,
        "consentType": row.consent_type,
        "status": row.status,
        "scope": row.scope,
        "risksDiscussed": parse_json(row.risks_discussed_json),
        "alternativesDiscussed": parse_json(row.alternatives_discussed_json),
        "costDiscussed": row.cost_discussed,
        "estimateRef": row.estimate_ref,
        "clientAuthorisedBy": row.client_authorised_by,
        "clientAuthorisedAt": row.client_authorised_at.isoformat() if row.client_authorised_at else None,
        "clientContactMethod": row.client_contact_method,
        "communicationNotes": row.communication_notes,
        "recordedBy": row.recorded_by,
        "witness": row.witness,
        "withdrawnAt": row.withdrawn_at.isoformat() if row.withdrawn_at else None,
        "evidenceEventRef": row.evidence_event_ref,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
    }


@router.post("/events")
def create_event(payload: EvidenceEventCreate, session: Session = Depends(get_session)) -> dict[str, Any]:
    try:
        event, created = create_evidence_event(
            session,
            event_type=payload.eventType,
            action=payload.action,
            patient_case_id=payload.patientCaseId,
            referral_episode_id=payload.referralEpisodeId,
            schedule_block_id=payload.scheduleBlockId,
            actor_id=payload.actorId,
            actor_name=payload.actorName,
            actor_role=payload.actorRole,
            actor_auth_source=payload.actorAuthSource,
            professional_role=payload.professionalRole,
            previous_state=payload.previousState,
            new_state=payload.newState,
            reason=payload.reason,
            justification=payload.justification,
            evidence_links=payload.evidenceLinks,
            alternatives_discussed=payload.alternativesDiscussed,
            client_authorisation=payload.clientAuthorisation,
            ai_system=payload.aiSystem,
            ai_model=payload.aiModel,
            ai_prompt_ref=payload.aiPromptRef,
            ai_output_ref=payload.aiOutputRef,
            ai_confidence=payload.aiConfidence,
            human_reviewer=payload.humanReviewer,
            human_review_status=payload.humanReviewStatus,
            supervisor_required=payload.supervisorRequired,
            supervisor_name=payload.supervisorName,
            supervisor_approval_status=payload.supervisorApprovalStatus,
            override_reason=payload.overrideReason,
            compliance_domain=payload.complianceDomain,
            risk_level=payload.riskLevel,
            source_module=payload.sourceModule,
            source_system=payload.sourceSystem,
            source_record_ref=payload.sourceRecordRef,
            correlation_id=payload.correlationId,
            causation_event_ref=payload.causationEventRef,
            idempotency_key=payload.idempotencyKey,
            request_id=payload.requestId,
            entity_type=payload.entityType,
            entity_id=payload.entityId,
            occurred_at=payload.occurredAt,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    session.commit()
    session.refresh(event)
    approval = session.exec(select(ApprovalTask).where(ApprovalTask.evidence_event_ref == event.event_ref)).first()
    return {"event": _event_dict(event, approval), "created": created}


@router.get("/events")
def list_evidence_events(
    patient_case_id: str | None = None,
    referral_episode_id: str | None = None,
    event_type: str | None = None,
    risk_level: str | None = None,
    limit: int = Query(default=250, ge=1, le=2000),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    query = select(EvidenceEvent).order_by(EvidenceEvent.created_at.desc())
    if patient_case_id:
        query = query.where(EvidenceEvent.patient_case_id == patient_case_id)
    if referral_episode_id:
        query = query.where(EvidenceEvent.referral_episode_id == referral_episode_id)
    if event_type:
        query = query.where(EvidenceEvent.event_type == event_type)
    if risk_level:
        query = query.where(EvidenceEvent.risk_level == risk_level)
    rows = session.exec(query.limit(limit)).all()
    refs = [row.event_ref for row in rows]
    approvals = session.exec(select(ApprovalTask).where(ApprovalTask.evidence_event_ref.in_(refs))).all() if refs else []
    approval_by_ref = {row.evidence_event_ref: row for row in approvals}
    return {"events": [_event_dict(row, approval_by_ref.get(row.event_ref)) for row in rows], "count": len(rows)}


@router.get("/integrity")
def evidence_integrity(session: Session = Depends(get_session)) -> dict[str, Any]:
    return verify_event_chain(session)


@router.post("/estimates")
def create_estimate_version(payload: EstimateVersionCreate, session: Session = Depends(get_session)) -> dict[str, Any]:
    request_data = payload.model_dump(mode="json")
    idempotency_key = payload.idempotencyKey or _request_fingerprint(f"estimate:{payload.estimateRef}", request_data)
    existing = session.exec(select(EstimateVersion).where(EstimateVersion.idempotency_key == idempotency_key)).first()
    if existing:
        return {"estimate": _estimate_dict(existing), "created": False}

    previous = session.exec(
        select(EstimateVersion)
        .where(EstimateVersion.estimate_ref == payload.estimateRef)
        .order_by(EstimateVersion.version.desc())
    ).first()
    version = previous.version + 1 if previous else 1
    client_notified = _now() if payload.clientDecision != "not_recorded" else None
    row = EstimateVersion(
        estimate_ref=payload.estimateRef,
        patient_case_id=payload.patientCaseId,
        referral_episode_id=payload.referralEpisodeId,
        version=version,
        supersedes_version=previous.version if previous else None,
        idempotency_key=idempotency_key,
        status=payload.status,
        lower_amount=payload.lowerAmount,
        upper_amount=payload.upperAmount,
        approved_ceiling=payload.approvedCeiling,
        currency=payload.currency,
        assumptions_json=json_text(payload.assumptions),
        itemised_lines_json=json_text(payload.itemisedLines),
        excluded_items_json=json_text(payload.excludedItems),
        insurance_assumptions_json=json_text(payload.insuranceAssumptions),
        alternatives_json=json_text(payload.alternatives),
        change_reason=payload.changeReason,
        client_contact_method=payload.clientContactMethod,
        client_contact_attempted_at=payload.clientContactAttemptedAt,
        client_notified_at=client_notified,
        client_decision=payload.clientDecision,
        emergency_authority=payload.emergencyAuthority,
        clinician_justification=payload.clinicianJustification,
        created_by=payload.createdBy,
    )
    session.add(row)
    session.flush()
    event, _ = create_evidence_event(
        session,
        event_type="estimate_version",
        action=f"estimate version {version} recorded: {payload.status} / {payload.clientDecision}",
        patient_case_id=payload.patientCaseId,
        referral_episode_id=payload.referralEpisodeId,
        actor_name=payload.createdBy,
        actor_role=payload.createdByRole,
        actor_auth_source="payload_unverified",
        previous_state=_estimate_dict(previous) if previous else None,
        new_state=_estimate_dict(row),
        reason=payload.changeReason or "versioned estimate recorded",
        justification=payload.clinicianJustification,
        evidence_links=[{"type": "estimate", "id": payload.estimateRef, "version": version}],
        client_authorisation={"decision": payload.clientDecision, "approvedCeiling": payload.approvedCeiling},
        supervisor_required=payload.emergencyAuthority,
        supervisor_approval_status="pending" if payload.emergencyAuthority else "not_required",
        compliance_domain="client_information",
        risk_level="red" if payload.emergencyAuthority or payload.clientDecision in {"declined", "unable_to_contact"} else "green" if payload.clientDecision == "accepted" else "amber",
        source_module="evidence-estimates",
        source_record_ref=f"{payload.estimateRef}:v{version}",
        entity_type="estimate",
        entity_id=payload.estimateRef,
        idempotency_key=f"event:{idempotency_key}",
    )
    row.evidence_event_ref = event.event_ref
    session.add(row)
    session.commit()
    session.refresh(row)
    return {"estimate": _estimate_dict(row), "created": True}


@router.get("/estimates/{estimate_ref}")
def list_estimate_versions(estimate_ref: str, session: Session = Depends(get_session)) -> dict[str, Any]:
    rows = session.exec(
        select(EstimateVersion)
        .where(EstimateVersion.estimate_ref == estimate_ref)
        .order_by(EstimateVersion.version)
    ).all()
    return {"estimateRef": estimate_ref, "versions": [_estimate_dict(row) for row in rows], "count": len(rows)}


@router.post("/consents")
def create_consent_record(payload: ConsentRecordCreate, session: Session = Depends(get_session)) -> dict[str, Any]:
    request_data = payload.model_dump(mode="json")
    idempotency_key = payload.idempotencyKey or _request_fingerprint(f"consent:{payload.consentRef}", request_data)
    existing = session.exec(select(ConsentRecord).where(ConsentRecord.idempotency_key == idempotency_key)).first()
    if existing:
        return {"consent": _consent_dict(existing), "created": False}

    previous = session.exec(
        select(ConsentRecord)
        .where(ConsentRecord.consent_ref == payload.consentRef)
        .order_by(ConsentRecord.version.desc())
    ).first()
    version = previous.version + 1 if previous else 1
    authorised = payload.status.lower() in {"authorised", "authorized", "clear", "approved"}
    withdrawn = payload.status.lower() in {"withdrawn", "revoked"}
    row = ConsentRecord(
        consent_ref=payload.consentRef,
        patient_case_id=payload.patientCaseId,
        referral_episode_id=payload.referralEpisodeId,
        version=version,
        supersedes_consent_ref=payload.supersedesConsentRef or (previous.consent_ref if previous else None),
        idempotency_key=idempotency_key,
        consent_type=payload.consentType,
        status=payload.status,
        scope=payload.scope,
        risks_discussed_json=json_text(payload.risksDiscussed),
        alternatives_discussed_json=json_text(payload.alternativesDiscussed),
        cost_discussed=payload.costDiscussed,
        estimate_ref=payload.estimateRef,
        client_authorised_by=payload.clientAuthorisedBy,
        client_authorised_at=_now() if authorised else None,
        client_contact_method=payload.clientContactMethod,
        communication_notes=payload.communicationNotes,
        recorded_by=payload.recordedBy,
        witness=payload.witness,
        withdrawn_at=_now() if withdrawn else None,
    )
    session.add(row)
    session.flush()
    links: list[dict[str, Any]] = [{"type": "consent", "id": payload.consentRef, "version": version}]
    if payload.estimateRef:
        links.append({"type": "estimate", "id": payload.estimateRef})
    event, _ = create_evidence_event(
        session,
        event_type="consent_record",
        action=f"consent version {version} recorded: {payload.status}",
        patient_case_id=payload.patientCaseId,
        referral_episode_id=payload.referralEpisodeId,
        actor_name=payload.recordedBy,
        actor_role=payload.recordedByRole,
        actor_auth_source="payload_unverified",
        previous_state=_consent_dict(previous) if previous else None,
        new_state=_consent_dict(row),
        reason="client consent state recorded",
        justification=payload.communicationNotes,
        evidence_links=links,
        alternatives_discussed=payload.alternativesDiscussed,
        client_authorisation={
            "authorisedBy": payload.clientAuthorisedBy,
            "status": payload.status,
            "scope": payload.scope,
            "method": payload.clientContactMethod,
        },
        supervisor_required=withdrawn,
        supervisor_approval_status="pending" if withdrawn else "not_required",
        compliance_domain="consent",
        risk_level="green" if authorised else "red" if withdrawn else "amber",
        source_module="evidence-consent",
        source_record_ref=f"{payload.consentRef}:v{version}",
        entity_type="consent",
        entity_id=payload.consentRef,
        idempotency_key=f"event:{idempotency_key}",
    )
    row.evidence_event_ref = event.event_ref
    session.add(row)
    session.commit()
    session.refresh(row)
    return {"consent": _consent_dict(row), "created": True}


@router.get("/consents")
def list_consent_records(
    patient_case_id: str | None = None,
    referral_episode_id: str | None = None,
    consent_ref: str | None = None,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    query = select(ConsentRecord).order_by(ConsentRecord.created_at.desc())
    if patient_case_id:
        query = query.where(ConsentRecord.patient_case_id == patient_case_id)
    if referral_episode_id:
        query = query.where(ConsentRecord.referral_episode_id == referral_episode_id)
    if consent_ref:
        query = query.where(ConsentRecord.consent_ref == consent_ref)
    rows = session.exec(query).all()
    return {"consents": [_consent_dict(row) for row in rows], "count": len(rows)}
