from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.database import get_session
from app.evidence_event_models import ConsentRecord, EstimateVersion, EvidenceEvent

router = APIRouter(prefix="/api/evidence", tags=["evidence-events"])


class EvidenceEventCreate(BaseModel):
    eventType: str
    patientCaseId: str | None = None
    referralEpisodeId: str | None = None
    scheduleBlockId: str | None = None
    actorId: str | None = None
    actorName: str = "frontend"
    actorRole: str = "user"
    professionalRole: str | None = None
    action: str
    previousState: dict[str, Any] | None = None
    newState: dict[str, Any] | None = None
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


class EstimateVersionCreate(BaseModel):
    estimateRef: str
    patientCaseId: str
    referralEpisodeId: str | None = None
    status: str = "draft"
    lowerAmount: float | None = None
    upperAmount: float | None = None
    currency: str = "GBP"
    assumptions: list[str] | dict[str, Any] | None = None
    itemisedLines: list[dict[str, Any]] | None = None
    excludedItems: list[str] | None = None
    insuranceAssumptions: dict[str, Any] | None = None
    alternatives: list[dict[str, Any]] | None = None
    clientDecision: str = "not_recorded"
    emergencyAuthority: bool = False
    clinicianJustification: str | None = None
    createdBy: str = "frontend"


class ConsentRecordCreate(BaseModel):
    consentRef: str
    patientCaseId: str
    referralEpisodeId: str | None = None
    consentType: str = "procedure"
    status: str = "pending"
    scope: str = "not_recorded"
    risksDiscussed: list[str] | None = None
    alternativesDiscussed: list[str] | None = None
    costDiscussed: bool = False
    estimateRef: str | None = None
    clientAuthorisedBy: str | None = None
    recordedBy: str = "frontend"
    witness: str | None = None
    evidenceEventRef: str | None = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _json(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, default=str)


def _parse(value: str | None) -> Any:
    if not value:
        return None
    try:
        return json.loads(value)
    except Exception:
        return value


def _event_ref() -> str:
    return f"evidence-{int(_now().timestamp() * 1000)}"


def _event_dict(row: EvidenceEvent) -> dict[str, Any]:
    return {
        "id": row.id,
        "eventRef": row.event_ref,
        "eventType": row.event_type,
        "patientCaseId": row.patient_case_id,
        "referralEpisodeId": row.referral_episode_id,
        "scheduleBlockId": row.schedule_block_id,
        "actorId": row.actor_id,
        "actorName": row.actor_name,
        "actorRole": row.actor_role,
        "professionalRole": row.professional_role,
        "action": row.action,
        "previousState": _parse(row.previous_state_json),
        "newState": _parse(row.new_state_json),
        "reason": row.reason,
        "justification": row.justification,
        "evidenceLinks": _parse(row.evidence_links_json),
        "alternativesDiscussed": _parse(row.alternatives_discussed_json),
        "clientAuthorisation": _parse(row.client_authorisation_json),
        "aiSystem": row.ai_system,
        "aiModel": row.ai_model,
        "aiPromptRef": row.ai_prompt_ref,
        "aiOutputRef": row.ai_output_ref,
        "aiConfidence": row.ai_confidence,
        "humanReviewer": row.human_reviewer,
        "humanReviewStatus": row.human_review_status,
        "supervisorRequired": row.supervisor_required,
        "supervisorName": row.supervisor_name,
        "supervisorApprovalStatus": row.supervisor_approval_status,
        "overrideReason": row.override_reason,
        "complianceDomain": row.compliance_domain,
        "riskLevel": row.risk_level,
        "sourceModule": row.source_module,
        "immutable": row.immutable,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
    }


def _estimate_dict(row: EstimateVersion) -> dict[str, Any]:
    return {
        "id": row.id,
        "estimateRef": row.estimate_ref,
        "patientCaseId": row.patient_case_id,
        "referralEpisodeId": row.referral_episode_id,
        "version": row.version,
        "status": row.status,
        "lowerAmount": row.lower_amount,
        "upperAmount": row.upper_amount,
        "currency": row.currency,
        "assumptions": _parse(row.assumptions_json),
        "itemisedLines": _parse(row.itemised_lines_json),
        "excludedItems": _parse(row.excluded_items_json),
        "insuranceAssumptions": _parse(row.insurance_assumptions_json),
        "alternatives": _parse(row.alternatives_json),
        "clientNotifiedAt": row.client_notified_at.isoformat() if row.client_notified_at else None,
        "clientDecision": row.client_decision,
        "emergencyAuthority": row.emergency_authority,
        "clinicianJustification": row.clinician_justification,
        "createdBy": row.created_by,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
    }


def _consent_dict(row: ConsentRecord) -> dict[str, Any]:
    return {
        "id": row.id,
        "consentRef": row.consent_ref,
        "patientCaseId": row.patient_case_id,
        "referralEpisodeId": row.referral_episode_id,
        "consentType": row.consent_type,
        "status": row.status,
        "scope": row.scope,
        "risksDiscussed": _parse(row.risks_discussed_json),
        "alternativesDiscussed": _parse(row.alternatives_discussed_json),
        "costDiscussed": row.cost_discussed,
        "estimateRef": row.estimate_ref,
        "clientAuthorisedBy": row.client_authorised_by,
        "clientAuthorisedAt": row.client_authorised_at.isoformat() if row.client_authorised_at else None,
        "recordedBy": row.recorded_by,
        "witness": row.witness,
        "evidenceEventRef": row.evidence_event_ref,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
    }


@router.post("/events")
def create_evidence_event(payload: EvidenceEventCreate, session: Session = Depends(get_session)) -> dict[str, Any]:
    row = EvidenceEvent(
        event_ref=_event_ref(),
        event_type=payload.eventType,
        patient_case_id=payload.patientCaseId,
        referral_episode_id=payload.referralEpisodeId,
        schedule_block_id=payload.scheduleBlockId,
        actor_id=payload.actorId,
        actor_name=payload.actorName,
        actor_role=payload.actorRole,
        professional_role=payload.professionalRole,
        action=payload.action,
        previous_state_json=_json(payload.previousState),
        new_state_json=_json(payload.newState),
        reason=payload.reason,
        justification=payload.justification,
        evidence_links_json=_json(payload.evidenceLinks),
        alternatives_discussed_json=_json(payload.alternativesDiscussed),
        client_authorisation_json=_json(payload.clientAuthorisation),
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
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return {"event": _event_dict(row)}


@router.get("/events")
def list_evidence_events(patient_case_id: str | None = None, referral_episode_id: str | None = None, session: Session = Depends(get_session)) -> dict[str, Any]:
    query = select(EvidenceEvent).order_by(EvidenceEvent.created_at.desc())
    rows = session.exec(query).all()
    if patient_case_id:
        rows = [row for row in rows if row.patient_case_id == patient_case_id]
    if referral_episode_id:
        rows = [row for row in rows if row.referral_episode_id == referral_episode_id]
    return {"events": [_event_dict(row) for row in rows], "count": len(rows)}


@router.post("/estimates")
def create_estimate_version(payload: EstimateVersionCreate, session: Session = Depends(get_session)) -> dict[str, Any]:
    previous = session.exec(select(EstimateVersion).where(EstimateVersion.estimate_ref == payload.estimateRef).order_by(EstimateVersion.version.desc())).first()
    row = EstimateVersion(
        estimate_ref=payload.estimateRef,
        patient_case_id=payload.patientCaseId,
        referral_episode_id=payload.referralEpisodeId,
        version=(previous.version + 1) if previous else 1,
        status=payload.status,
        lower_amount=payload.lowerAmount,
        upper_amount=payload.upperAmount,
        currency=payload.currency,
        assumptions_json=_json(payload.assumptions),
        itemised_lines_json=_json(payload.itemisedLines),
        excluded_items_json=_json(payload.excludedItems),
        insurance_assumptions_json=_json(payload.insuranceAssumptions),
        alternatives_json=_json(payload.alternatives),
        client_decision=payload.clientDecision,
        emergency_authority=payload.emergencyAuthority,
        clinician_justification=payload.clinicianJustification,
        created_by=payload.createdBy,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return {"estimate": _estimate_dict(row)}


@router.get("/estimates/{estimate_ref}")
def list_estimate_versions(estimate_ref: str, session: Session = Depends(get_session)) -> dict[str, Any]:
    rows = session.exec(select(EstimateVersion).where(EstimateVersion.estimate_ref == estimate_ref).order_by(EstimateVersion.version)).all()
    return {"estimateRef": estimate_ref, "versions": [_estimate_dict(row) for row in rows], "count": len(rows)}


@router.post("/consents")
def create_consent_record(payload: ConsentRecordCreate, session: Session = Depends(get_session)) -> dict[str, Any]:
    existing = session.exec(select(ConsentRecord).where(ConsentRecord.consent_ref == payload.consentRef)).first()
    if existing:
        raise HTTPException(status_code=409, detail="consent record already exists; create a new consent_ref for a new record")
    row = ConsentRecord(
        consent_ref=payload.consentRef,
        patient_case_id=payload.patientCaseId,
        referral_episode_id=payload.referralEpisodeId,
        consent_type=payload.consentType,
        status=payload.status,
        scope=payload.scope,
        risks_discussed_json=_json(payload.risksDiscussed),
        alternatives_discussed_json=_json(payload.alternativesDiscussed),
        cost_discussed=payload.costDiscussed,
        estimate_ref=payload.estimateRef,
        client_authorised_by=payload.clientAuthorisedBy,
        client_authorised_at=_now() if payload.status in {"authorised", "authorized", "clear", "approved"} else None,
        recorded_by=payload.recordedBy,
        witness=payload.witness,
        evidence_event_ref=payload.evidenceEventRef,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return {"consent": _consent_dict(row)}


@router.get("/consents")
def list_consent_records(patient_case_id: str | None = None, referral_episode_id: str | None = None, session: Session = Depends(get_session)) -> dict[str, Any]:
    rows = session.exec(select(ConsentRecord).order_by(ConsentRecord.created_at.desc())).all()
    if patient_case_id:
        rows = [row for row in rows if row.patient_case_id == patient_case_id]
    if referral_episode_id:
        rows = [row for row in rows if row.referral_episode_id == referral_episode_id]
    return {"consents": [_consent_dict(row) for row in rows], "count": len(rows)}
