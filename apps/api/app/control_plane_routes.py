from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field as PydanticField
from sqlmodel import Session, select

from app.control_plane_models import (
    AIModelRegistration,
    AccountableHandover,
    ComplianceControl,
    CriticalResultAcknowledgement,
    ServiceAvailability,
)
from app.database import get_session
from app.evidence_approval_models import ApprovalTask
from app.evidence_event_models import EvidenceEvent
from app.evidence_service import create_evidence_event, json_text, parse_json

router = APIRouter(prefix="/api/control-plane", tags=["control-plane"])


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def ref(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def clean_status(value: str, allowed: set[str], label: str) -> str:
    normal = value.lower().strip()
    if normal not in allowed:
        raise HTTPException(status_code=400, detail=f"{label} must be one of: {', '.join(sorted(allowed))}")
    return normal


class HandoverCreate(BaseModel):
    handoverRef: str | None = None
    patientCaseId: str | None = None
    referralEpisodeId: str
    fromActor: str
    fromRole: str
    toActor: str | None = None
    toRole: str
    summary: str
    clinicalRisks: list[str] = PydanticField(default_factory=list)
    outstandingActions: list[dict[str, Any] | str] = PydanticField(default_factory=list)
    escalationThreshold: str | None = None
    dueAt: datetime | None = None


class HandoverDecision(BaseModel):
    decision: str
    decidedBy: str
    decidedByRole: str
    note: str | None = None


class ComplianceControlCreate(BaseModel):
    controlRef: str | None = None
    premisesRef: str = "default-premises"
    domain: str
    title: str
    requirementSource: str | None = None
    responsibleRole: str
    responsibleActor: str | None = None
    evidenceRequired: list[str] = PydanticField(default_factory=list)
    status: str = "not_assessed"
    riskLevel: str = "amber"
    reviewFrequencyDays: int = 90
    nextReviewAt: datetime | None = None
    correctiveAction: str | None = None
    updatedBy: str = "control-plane-ui"
    updatedByRole: str = "ops_manager"


class ComplianceControlUpdate(BaseModel):
    status: str
    riskLevel: str | None = None
    responsibleActor: str | None = None
    correctiveAction: str | None = None
    nextReviewAt: datetime | None = None
    reviewedBy: str
    reviewedByRole: str
    note: str | None = None


class ServiceAvailabilityCreate(BaseModel):
    serviceRef: str
    premisesRef: str = "default-premises"
    department: str
    serviceName: str
    declaredCapability: str = "available"
    operationalStatus: str = "available"
    acceptingReferrals: bool = True
    staffingReady: bool = True
    equipmentReady: bool = True
    consumablesReady: bool = True
    limitingReason: str | None = None
    effectiveFrom: datetime | None = None
    expectedRestoreAt: datetime | None = None
    updatedBy: str
    updatedByRole: str = "ops_manager"


class AIModelCreate(BaseModel):
    modelRef: str | None = None
    provider: str
    modelName: str
    modelVersion: str
    purpose: str
    riskClass: str = "administrative"
    status: str = "draft"
    approvedRoles: list[str] = PydanticField(default_factory=list)
    permittedData: list[str] = PydanticField(default_factory=list)
    prohibitedData: list[str] = PydanticField(default_factory=list)
    dataLocation: str | None = None
    retentionPolicy: str | None = None
    trainingUseStatus: str = "prohibited"
    humanReviewRule: str = "required"
    knownLimitations: str | None = None
    validationSummary: str | None = None
    fallbackProcess: str | None = None
    accountableOwner: str
    nextReviewAt: datetime | None = None
    createdBy: str = "ai-governance-ui"
    createdByRole: str = "governance_lead"


class AIModelReview(BaseModel):
    decision: str
    reviewedBy: str
    reviewedByRole: str
    validationSummary: str | None = None
    knownLimitations: str | None = None
    fallbackProcess: str | None = None
    nextReviewAt: datetime | None = None
    note: str | None = None


class CriticalResultCreate(BaseModel):
    resultRef: str
    patientCaseId: str | None = None
    referralEpisodeId: str
    resultType: str
    severity: str = "red"
    summary: str
    assignedTo: str
    assignedRole: str
    dueAt: datetime | None = None
    createdBy: str = "integration"


class CriticalResultDecision(BaseModel):
    acknowledgedBy: str
    acknowledgedByRole: str
    actionTaken: str
    note: str | None = None


def handover_dict(row: AccountableHandover) -> dict[str, Any]:
    return {
        "id": row.id,
        "handoverRef": row.handover_ref,
        "patientCaseId": row.patient_case_id,
        "referralEpisodeId": row.referral_episode_id,
        "fromActor": row.from_actor,
        "fromRole": row.from_role,
        "toActor": row.to_actor,
        "toRole": row.to_role,
        "status": row.status,
        "summary": row.summary,
        "clinicalRisks": parse_json(row.clinical_risks_json) or [],
        "outstandingActions": parse_json(row.outstanding_actions_json) or [],
        "escalationThreshold": row.escalation_threshold,
        "dueAt": row.due_at.isoformat() if row.due_at else None,
        "acceptedBy": row.accepted_by,
        "acceptedByRole": row.accepted_by_role,
        "acceptedAt": row.accepted_at.isoformat() if row.accepted_at else None,
        "decisionNote": row.decision_note,
        "evidenceEventRef": row.evidence_event_ref,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
    }


def control_dict(row: ComplianceControl) -> dict[str, Any]:
    return {
        "id": row.id,
        "controlRef": row.control_ref,
        "premisesRef": row.premises_ref,
        "domain": row.domain,
        "title": row.title,
        "requirementSource": row.requirement_source,
        "responsibleRole": row.responsible_role,
        "responsibleActor": row.responsible_actor,
        "evidenceRequired": parse_json(row.evidence_required_json) or [],
        "status": row.status,
        "riskLevel": row.risk_level,
        "reviewFrequencyDays": row.review_frequency_days,
        "nextReviewAt": row.next_review_at.isoformat() if row.next_review_at else None,
        "lastReviewedAt": row.last_reviewed_at.isoformat() if row.last_reviewed_at else None,
        "correctiveAction": row.corrective_action,
        "evidenceEventRef": row.evidence_event_ref,
        "updatedAt": row.updated_at.isoformat() if row.updated_at else None,
    }


def service_dict(row: ServiceAvailability) -> dict[str, Any]:
    return {
        "id": row.id,
        "serviceRef": row.service_ref,
        "premisesRef": row.premises_ref,
        "department": row.department,
        "serviceName": row.service_name,
        "declaredCapability": row.declared_capability,
        "operationalStatus": row.operational_status,
        "acceptingReferrals": row.accepting_referrals,
        "staffingReady": row.staffing_ready,
        "equipmentReady": row.equipment_ready,
        "consumablesReady": row.consumables_ready,
        "limitingReason": row.limiting_reason,
        "effectiveFrom": row.effective_from.isoformat() if row.effective_from else None,
        "expectedRestoreAt": row.expected_restore_at.isoformat() if row.expected_restore_at else None,
        "updatedBy": row.updated_by,
        "evidenceEventRef": row.evidence_event_ref,
        "updatedAt": row.updated_at.isoformat() if row.updated_at else None,
    }


def ai_model_dict(row: AIModelRegistration) -> dict[str, Any]:
    return {
        "id": row.id,
        "modelRef": row.model_ref,
        "provider": row.provider,
        "modelName": row.model_name,
        "modelVersion": row.model_version,
        "purpose": row.purpose,
        "riskClass": row.risk_class,
        "status": row.status,
        "approvedRoles": parse_json(row.approved_roles_json) or [],
        "permittedData": parse_json(row.permitted_data_json) or [],
        "prohibitedData": parse_json(row.prohibited_data_json) or [],
        "dataLocation": row.data_location,
        "retentionPolicy": row.retention_policy,
        "trainingUseStatus": row.training_use_status,
        "humanReviewRule": row.human_review_rule,
        "knownLimitations": row.known_limitations,
        "validationSummary": row.validation_summary,
        "fallbackProcess": row.fallback_process,
        "accountableOwner": row.accountable_owner,
        "approvedBy": row.approved_by,
        "approvedAt": row.approved_at.isoformat() if row.approved_at else None,
        "nextReviewAt": row.next_review_at.isoformat() if row.next_review_at else None,
        "evidenceEventRef": row.evidence_event_ref,
        "updatedAt": row.updated_at.isoformat() if row.updated_at else None,
    }


def critical_result_dict(row: CriticalResultAcknowledgement) -> dict[str, Any]:
    return {
        "id": row.id,
        "resultRef": row.result_ref,
        "patientCaseId": row.patient_case_id,
        "referralEpisodeId": row.referral_episode_id,
        "resultType": row.result_type,
        "severity": row.severity,
        "summary": row.summary,
        "status": row.status,
        "assignedTo": row.assigned_to,
        "assignedRole": row.assigned_role,
        "dueAt": row.due_at.isoformat() if row.due_at else None,
        "acknowledgedBy": row.acknowledged_by,
        "acknowledgedAt": row.acknowledged_at.isoformat() if row.acknowledged_at else None,
        "actionTaken": row.action_taken,
        "evidenceEventRef": row.evidence_event_ref,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
    }


@router.post("/handovers")
def create_handover(payload: HandoverCreate, session: Session = Depends(get_session)) -> dict[str, Any]:
    handover_ref = payload.handoverRef or ref("handover")
    if session.exec(select(AccountableHandover).where(AccountableHandover.handover_ref == handover_ref)).first():
        raise HTTPException(status_code=409, detail="handover_ref already exists")
    row = AccountableHandover(
        handover_ref=handover_ref,
        patient_case_id=payload.patientCaseId,
        referral_episode_id=payload.referralEpisodeId,
        from_actor=payload.fromActor,
        from_role=payload.fromRole,
        to_actor=payload.toActor,
        to_role=payload.toRole,
        status="pending",
        summary=payload.summary,
        clinical_risks_json=json_text(payload.clinicalRisks),
        outstanding_actions_json=json_text(payload.outstandingActions),
        escalation_threshold=payload.escalationThreshold,
        due_at=payload.dueAt,
    )
    session.add(row)
    session.flush()
    event, _ = create_evidence_event(
        session,
        event_type="handover_created",
        action="accountable handover created",
        patient_case_id=payload.patientCaseId,
        referral_episode_id=payload.referralEpisodeId,
        actor_name=payload.fromActor,
        actor_role=payload.fromRole,
        actor_auth_source="payload_unverified",
        new_state=handover_dict(row),
        reason="responsibility transfer requires explicit acceptance",
        evidence_links=[{"type": "handover", "id": handover_ref}],
        compliance_domain="clinical_governance",
        risk_level="amber" if not payload.clinicalRisks else "red",
        source_module="control-plane",
        source_record_ref=handover_ref,
        entity_type="handover",
        entity_id=handover_ref,
        idempotency_key=f"handover:create:{handover_ref}",
    )
    row.evidence_event_ref = event.event_ref
    session.add(row)
    session.commit()
    session.refresh(row)
    return {"handover": handover_dict(row)}


@router.get("/handovers")
def list_handovers(status: str | None = None, referral_episode_id: str | None = None, session: Session = Depends(get_session)) -> dict[str, Any]:
    query = select(AccountableHandover).order_by(AccountableHandover.created_at.desc())
    if status:
        query = query.where(AccountableHandover.status == status)
    if referral_episode_id:
        query = query.where(AccountableHandover.referral_episode_id == referral_episode_id)
    rows = session.exec(query).all()
    return {"handovers": [handover_dict(row) for row in rows], "count": len(rows)}


@router.patch("/handovers/{handover_id}/decision")
def decide_handover(handover_id: int, payload: HandoverDecision, session: Session = Depends(get_session)) -> dict[str, Any]:
    row = session.get(AccountableHandover, handover_id)
    if not row:
        raise HTTPException(status_code=404, detail="handover not found")
    if row.status != "pending":
        raise HTTPException(status_code=409, detail="handover already decided")
    decision = clean_status(payload.decision, {"accepted", "rejected", "escalated"}, "decision")
    previous = handover_dict(row)
    row.status = decision
    row.accepted_by = payload.decidedBy
    row.accepted_by_role = payload.decidedByRole
    row.accepted_at = utc_now()
    row.decision_note = payload.note
    session.add(row)
    event, _ = create_evidence_event(
        session,
        event_type="handover_decision",
        action=f"handover {decision}",
        patient_case_id=row.patient_case_id,
        referral_episode_id=row.referral_episode_id,
        actor_name=payload.decidedBy,
        actor_role=payload.decidedByRole,
        actor_auth_source="payload_unverified",
        previous_state=previous,
        new_state=handover_dict(row),
        reason="named recipient decision",
        justification=payload.note,
        evidence_links=[{"type": "handover", "id": row.handover_ref}],
        compliance_domain="clinical_governance",
        risk_level="green" if decision == "accepted" else "red",
        source_module="control-plane",
        source_record_ref=row.handover_ref,
        causation_event_ref=row.evidence_event_ref,
        entity_type="handover",
        entity_id=row.handover_ref,
        idempotency_key=f"handover:decision:{row.handover_ref}:{decision}",
    )
    row.evidence_event_ref = event.event_ref
    session.add(row)
    session.commit()
    session.refresh(row)
    return {"handover": handover_dict(row)}


@router.post("/controls")
def create_control(payload: ComplianceControlCreate, session: Session = Depends(get_session)) -> dict[str, Any]:
    control_ref = payload.controlRef or ref("control")
    if session.exec(select(ComplianceControl).where(ComplianceControl.control_ref == control_ref)).first():
        raise HTTPException(status_code=409, detail="control_ref already exists")
    now = utc_now()
    row = ComplianceControl(
        control_ref=control_ref,
        premises_ref=payload.premisesRef,
        domain=payload.domain,
        title=payload.title,
        requirement_source=payload.requirementSource,
        responsible_role=payload.responsibleRole,
        responsible_actor=payload.responsibleActor,
        evidence_required_json=json_text(payload.evidenceRequired),
        status=payload.status,
        risk_level=payload.riskLevel,
        review_frequency_days=max(payload.reviewFrequencyDays, 1),
        next_review_at=payload.nextReviewAt,
        corrective_action=payload.correctiveAction,
        updated_at=now,
    )
    session.add(row)
    session.flush()
    event, _ = create_evidence_event(
        session,
        event_type="compliance_control_created",
        action="compliance control registered",
        actor_name=payload.updatedBy,
        actor_role=payload.updatedByRole,
        actor_auth_source="payload_unverified",
        new_state=control_dict(row),
        reason="premises control requires named ownership and evidence",
        compliance_domain=payload.domain,
        risk_level=payload.riskLevel,
        source_module="control-plane",
        source_record_ref=control_ref,
        entity_type="compliance_control",
        entity_id=control_ref,
        idempotency_key=f"control:create:{control_ref}",
    )
    row.evidence_event_ref = event.event_ref
    session.add(row)
    session.commit()
    session.refresh(row)
    return {"control": control_dict(row)}


@router.get("/controls")
def list_controls(status: str | None = None, premises_ref: str | None = None, session: Session = Depends(get_session)) -> dict[str, Any]:
    query = select(ComplianceControl).order_by(ComplianceControl.risk_level.desc(), ComplianceControl.updated_at.desc())
    if status:
        query = query.where(ComplianceControl.status == status)
    if premises_ref:
        query = query.where(ComplianceControl.premises_ref == premises_ref)
    rows = session.exec(query).all()
    return {"controls": [control_dict(row) for row in rows], "count": len(rows)}


@router.patch("/controls/{control_id}")
def update_control(control_id: int, payload: ComplianceControlUpdate, session: Session = Depends(get_session)) -> dict[str, Any]:
    row = session.get(ComplianceControl, control_id)
    if not row:
        raise HTTPException(status_code=404, detail="control not found")
    previous = control_dict(row)
    row.status = payload.status
    if payload.riskLevel is not None:
        row.risk_level = payload.riskLevel
    row.responsible_actor = payload.responsibleActor or row.responsible_actor
    row.corrective_action = payload.correctiveAction
    row.next_review_at = payload.nextReviewAt
    row.last_reviewed_at = utc_now()
    row.updated_at = utc_now()
    session.add(row)
    event, _ = create_evidence_event(
        session,
        event_type="compliance_control_reviewed",
        action=f"control status set to {row.status}",
        actor_name=payload.reviewedBy,
        actor_role=payload.reviewedByRole,
        actor_auth_source="payload_unverified",
        previous_state=previous,
        new_state=control_dict(row),
        reason="scheduled or exception-led control review",
        justification=payload.note or payload.correctiveAction,
        compliance_domain=row.domain,
        risk_level=row.risk_level,
        source_module="control-plane",
        source_record_ref=row.control_ref,
        causation_event_ref=row.evidence_event_ref,
        entity_type="compliance_control",
        entity_id=row.control_ref,
        idempotency_key=f"control:review:{row.control_ref}:{int(row.updated_at.timestamp())}",
    )
    row.evidence_event_ref = event.event_ref
    session.add(row)
    session.commit()
    session.refresh(row)
    return {"control": control_dict(row)}


@router.post("/services")
def upsert_service(payload: ServiceAvailabilityCreate, session: Session = Depends(get_session)) -> dict[str, Any]:
    status = clean_status(payload.operationalStatus, {"available", "reduced", "suspended", "unavailable"}, "operationalStatus")
    row = session.exec(select(ServiceAvailability).where(ServiceAvailability.service_ref == payload.serviceRef)).first()
    previous = service_dict(row) if row else None
    if not row:
        row = ServiceAvailability(
            service_ref=payload.serviceRef,
            premises_ref=payload.premisesRef,
            department=payload.department,
            service_name=payload.serviceName,
        )
    row.declared_capability = payload.declaredCapability
    row.operational_status = status
    row.accepting_referrals = payload.acceptingReferrals
    row.staffing_ready = payload.staffingReady
    row.equipment_ready = payload.equipmentReady
    row.consumables_ready = payload.consumablesReady
    row.limiting_reason = payload.limitingReason
    row.effective_from = payload.effectiveFrom or utc_now()
    row.expected_restore_at = payload.expectedRestoreAt
    row.updated_by = payload.updatedBy
    row.updated_at = utc_now()
    session.add(row)
    session.flush()
    risk = "green" if status == "available" and all([row.staffing_ready, row.equipment_ready, row.consumables_ready]) else "red"
    event, _ = create_evidence_event(
        session,
        event_type="service_availability_changed",
        action=f"{row.service_name} set to {status}",
        actor_name=payload.updatedBy,
        actor_role=payload.updatedByRole,
        actor_auth_source="payload_unverified",
        previous_state=previous,
        new_state=service_dict(row),
        reason=payload.limitingReason or "service state reviewed",
        compliance_domain="service_availability",
        risk_level=risk,
        source_module="control-plane",
        source_record_ref=row.service_ref,
        entity_type="service_availability",
        entity_id=row.service_ref,
        idempotency_key=f"service:{row.service_ref}:{int(row.updated_at.timestamp())}",
    )
    row.evidence_event_ref = event.event_ref
    session.add(row)
    session.commit()
    session.refresh(row)
    return {"service": service_dict(row)}


@router.get("/services")
def list_services(premises_ref: str | None = None, session: Session = Depends(get_session)) -> dict[str, Any]:
    query = select(ServiceAvailability).order_by(ServiceAvailability.department, ServiceAvailability.service_name)
    if premises_ref:
        query = query.where(ServiceAvailability.premises_ref == premises_ref)
    rows = session.exec(query).all()
    return {"services": [service_dict(row) for row in rows], "count": len(rows)}


@router.post("/ai-models")
def register_ai_model(payload: AIModelCreate, session: Session = Depends(get_session)) -> dict[str, Any]:
    model_ref = payload.modelRef or ref("model")
    if session.exec(select(AIModelRegistration).where(AIModelRegistration.model_ref == model_ref)).first():
        raise HTTPException(status_code=409, detail="model_ref already exists")
    row = AIModelRegistration(
        model_ref=model_ref,
        provider=payload.provider,
        model_name=payload.modelName,
        model_version=payload.modelVersion,
        purpose=payload.purpose,
        risk_class=payload.riskClass,
        status=payload.status,
        approved_roles_json=json_text(payload.approvedRoles),
        permitted_data_json=json_text(payload.permittedData),
        prohibited_data_json=json_text(payload.prohibitedData),
        data_location=payload.dataLocation,
        retention_policy=payload.retentionPolicy,
        training_use_status=payload.trainingUseStatus,
        human_review_rule=payload.humanReviewRule,
        known_limitations=payload.knownLimitations,
        validation_summary=payload.validationSummary,
        fallback_process=payload.fallbackProcess,
        accountable_owner=payload.accountableOwner,
        next_review_at=payload.nextReviewAt,
    )
    session.add(row)
    session.flush()
    event, _ = create_evidence_event(
        session,
        event_type="ai_model_registered",
        action="AI model registered for governance review",
        actor_name=payload.createdBy,
        actor_role=payload.createdByRole,
        actor_auth_source="payload_unverified",
        new_state=ai_model_dict(row),
        reason="AI use requires declared purpose, limits, data rules and accountable owner",
        ai_system=payload.provider,
        ai_model=f"{payload.modelName}:{payload.modelVersion}",
        human_review_status="required",
        supervisor_required=True,
        supervisor_approval_status="pending",
        compliance_domain="ai_governance",
        risk_level="red" if payload.riskClass in {"clinical_support", "high_consequence"} else "amber",
        source_module="control-plane",
        source_record_ref=model_ref,
        entity_type="ai_model",
        entity_id=model_ref,
        idempotency_key=f"ai-model:create:{model_ref}",
    )
    row.evidence_event_ref = event.event_ref
    session.add(row)
    session.commit()
    session.refresh(row)
    return {"model": ai_model_dict(row)}


@router.get("/ai-models")
def list_ai_models(status: str | None = None, session: Session = Depends(get_session)) -> dict[str, Any]:
    query = select(AIModelRegistration).order_by(AIModelRegistration.updated_at.desc())
    if status:
        query = query.where(AIModelRegistration.status == status)
    rows = session.exec(query).all()
    return {"models": [ai_model_dict(row) for row in rows], "count": len(rows)}


@router.patch("/ai-models/{model_id}/review")
def review_ai_model(model_id: int, payload: AIModelReview, session: Session = Depends(get_session)) -> dict[str, Any]:
    row = session.get(AIModelRegistration, model_id)
    if not row:
        raise HTTPException(status_code=404, detail="AI model registration not found")
    decision = clean_status(payload.decision, {"approved", "rejected", "suspended"}, "decision")
    previous = ai_model_dict(row)
    row.status = decision
    row.approved_by = payload.reviewedBy if decision == "approved" else None
    row.approved_at = utc_now() if decision == "approved" else None
    row.validation_summary = payload.validationSummary or row.validation_summary
    row.known_limitations = payload.knownLimitations or row.known_limitations
    row.fallback_process = payload.fallbackProcess or row.fallback_process
    row.next_review_at = payload.nextReviewAt
    row.updated_at = utc_now()
    session.add(row)
    event, _ = create_evidence_event(
        session,
        event_type="ai_model_review",
        action=f"AI model {decision}",
        actor_name=payload.reviewedBy,
        actor_role=payload.reviewedByRole,
        actor_auth_source="payload_unverified",
        previous_state=previous,
        new_state=ai_model_dict(row),
        reason="named AI governance decision",
        justification=payload.note or payload.validationSummary,
        ai_system=row.provider,
        ai_model=f"{row.model_name}:{row.model_version}",
        human_reviewer=payload.reviewedBy,
        human_review_status="accepted" if decision == "approved" else "rejected",
        compliance_domain="ai_governance",
        risk_level="green" if decision == "approved" else "red",
        source_module="control-plane",
        source_record_ref=row.model_ref,
        causation_event_ref=row.evidence_event_ref,
        entity_type="ai_model",
        entity_id=row.model_ref,
        idempotency_key=f"ai-model:review:{row.model_ref}:{decision}:{int(row.updated_at.timestamp())}",
    )
    row.evidence_event_ref = event.event_ref
    session.add(row)
    session.commit()
    session.refresh(row)
    return {"model": ai_model_dict(row)}


@router.post("/critical-results")
def create_critical_result(payload: CriticalResultCreate, session: Session = Depends(get_session)) -> dict[str, Any]:
    if session.exec(select(CriticalResultAcknowledgement).where(CriticalResultAcknowledgement.result_ref == payload.resultRef)).first():
        raise HTTPException(status_code=409, detail="result_ref already exists")
    row = CriticalResultAcknowledgement(
        result_ref=payload.resultRef,
        patient_case_id=payload.patientCaseId,
        referral_episode_id=payload.referralEpisodeId,
        result_type=payload.resultType,
        severity=payload.severity,
        summary=payload.summary,
        status="awaiting_acknowledgement",
        assigned_to=payload.assignedTo,
        assigned_role=payload.assignedRole,
        due_at=payload.dueAt,
    )
    session.add(row)
    session.flush()
    event, _ = create_evidence_event(
        session,
        event_type="critical_result_received",
        action="critical result awaiting acknowledgement",
        patient_case_id=payload.patientCaseId,
        referral_episode_id=payload.referralEpisodeId,
        actor_name=payload.createdBy,
        actor_role="integration",
        actor_auth_source="system_integration",
        new_state=critical_result_dict(row),
        reason=payload.summary,
        supervisor_required=True,
        supervisor_approval_status="pending",
        compliance_domain="diagnostics",
        risk_level="red",
        source_module="control-plane",
        source_record_ref=payload.resultRef,
        entity_type="critical_result",
        entity_id=payload.resultRef,
        idempotency_key=f"critical-result:create:{payload.resultRef}",
    )
    row.evidence_event_ref = event.event_ref
    session.add(row)
    session.commit()
    session.refresh(row)
    return {"result": critical_result_dict(row)}


@router.get("/critical-results")
def list_critical_results(status: str | None = None, session: Session = Depends(get_session)) -> dict[str, Any]:
    query = select(CriticalResultAcknowledgement).order_by(CriticalResultAcknowledgement.created_at.desc())
    if status:
        query = query.where(CriticalResultAcknowledgement.status == status)
    rows = session.exec(query).all()
    return {"results": [critical_result_dict(row) for row in rows], "count": len(rows)}


@router.patch("/critical-results/{result_id}/acknowledge")
def acknowledge_critical_result(result_id: int, payload: CriticalResultDecision, session: Session = Depends(get_session)) -> dict[str, Any]:
    row = session.get(CriticalResultAcknowledgement, result_id)
    if not row:
        raise HTTPException(status_code=404, detail="critical result not found")
    if row.status != "awaiting_acknowledgement":
        raise HTTPException(status_code=409, detail="critical result already acknowledged")
    previous = critical_result_dict(row)
    row.status = "acknowledged"
    row.acknowledged_by = payload.acknowledgedBy
    row.acknowledged_at = utc_now()
    row.action_taken = payload.actionTaken
    session.add(row)
    event, _ = create_evidence_event(
        session,
        event_type="critical_result_acknowledged",
        action="critical result acknowledged and action recorded",
        patient_case_id=row.patient_case_id,
        referral_episode_id=row.referral_episode_id,
        actor_name=payload.acknowledgedBy,
        actor_role=payload.acknowledgedByRole,
        actor_auth_source="payload_unverified",
        previous_state=previous,
        new_state=critical_result_dict(row),
        reason=row.summary,
        justification=payload.note or payload.actionTaken,
        compliance_domain="diagnostics",
        risk_level="green",
        source_module="control-plane",
        source_record_ref=row.result_ref,
        causation_event_ref=row.evidence_event_ref,
        entity_type="critical_result",
        entity_id=row.result_ref,
        idempotency_key=f"critical-result:ack:{row.result_ref}",
    )
    row.evidence_event_ref = event.event_ref
    session.add(row)
    session.commit()
    session.refresh(row)
    return {"result": critical_result_dict(row)}


@router.get("/dashboard")
def control_plane_dashboard(session: Session = Depends(get_session)) -> dict[str, Any]:
    now = utc_now()
    handovers = session.exec(select(AccountableHandover).order_by(AccountableHandover.created_at.desc())).all()
    controls = session.exec(select(ComplianceControl).order_by(ComplianceControl.updated_at.desc())).all()
    services = session.exec(select(ServiceAvailability).order_by(ServiceAvailability.department, ServiceAvailability.service_name)).all()
    ai_models = session.exec(select(AIModelRegistration).order_by(AIModelRegistration.updated_at.desc())).all()
    results = session.exec(select(CriticalResultAcknowledgement).order_by(CriticalResultAcknowledgement.created_at.desc())).all()
    approvals = session.exec(select(ApprovalTask).where(ApprovalTask.status == "pending").order_by(ApprovalTask.requested_at.desc())).all()
    events = session.exec(select(EvidenceEvent).order_by(EvidenceEvent.created_at.desc()).limit(20)).all()

    overdue_handovers = [row for row in handovers if row.status == "pending" and row.due_at and row.due_at < now]
    overdue_controls = [row for row in controls if row.next_review_at and row.next_review_at < now]
    unsafe_services = [row for row in services if row.operational_status != "available" or not all([row.staffing_ready, row.equipment_ready, row.consumables_ready])]
    unapproved_models = [row for row in ai_models if row.status != "approved"]
    open_results = [row for row in results if row.status != "acknowledged"]
    red_controls = [row for row in controls if row.risk_level == "red" or row.status in {"failed", "non_compliant", "overdue"}]

    return {
        "generatedAt": now.isoformat(),
        "summary": {
            "pendingHandovers": len([row for row in handovers if row.status == "pending"]),
            "overdueHandovers": len(overdue_handovers),
            "redControls": len(red_controls),
            "overdueControls": len(overdue_controls),
            "unsafeServices": len(unsafe_services),
            "unapprovedAIModels": len(unapproved_models),
            "unacknowledgedCriticalResults": len(open_results),
            "pendingApprovals": len(approvals),
        },
        "handovers": [handover_dict(row) for row in handovers[:20]],
        "controls": [control_dict(row) for row in controls[:20]],
        "services": [service_dict(row) for row in services],
        "aiModels": [ai_model_dict(row) for row in ai_models],
        "criticalResults": [critical_result_dict(row) for row in results[:20]],
        "pendingApprovals": [
            {
                "id": row.id,
                "evidenceEventRef": row.evidence_event_ref,
                "status": row.status,
                "requiredRole": row.required_role,
                "reason": row.reason,
                "riskLevel": row.risk_level,
                "requestedBy": row.requested_by,
                "requestedAt": row.requested_at.isoformat() if row.requested_at else None,
            }
            for row in approvals
        ],
        "recentEvidence": [
            {
                "eventRef": row.event_ref,
                "eventType": row.event_type,
                "action": row.action,
                "riskLevel": row.risk_level,
                "complianceDomain": row.compliance_domain,
                "actorName": row.actor_name,
                "createdAt": row.created_at.isoformat() if row.created_at else None,
                "eventHash": row.event_hash,
            }
            for row in events
        ],
    }
