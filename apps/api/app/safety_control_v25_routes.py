from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.auth import AuthContext, require_authenticated, require_roles
from app.database import get_session
from app.safety_control_v25_models import (
    SafetyAccessEventV25,
    SafetyActionV25,
    SafetyDecisionV25,
    SafetyEscalationV25,
    SafetyLinkV25,
    SafetyRecordV25,
)
from app.safety_control_v25_service import (
    CONFIDENTIALITY,
    GOVERNANCE_ROLES,
    OPEN_RECORD_STATUSES,
    SENIOR_ROLES,
    SEVERITIES,
    action_dict,
    assign_owners,
    can_manage,
    can_view,
    close_record,
    closure_gate,
    create_action,
    create_decision,
    create_escalation,
    create_record,
    decision_dict,
    escalate if False else create_escalation,
    escalation_dict,
    evaluate_overdue,
    is_conflicted,
    link_dict,
    public_record_dict,
    record_access,
    reopen_record,
    require_action,
    require_expected_version,
    require_record,
    review_closure,
    sensitive_record_dict,
    utc_now,
    verify_action,
    complete_action,
)

router = APIRouter(prefix="/api/v25/safety", tags=["cross-system-safety-control-v25"])
SENIOR_ROLE_TUPLE = tuple(sorted(SENIOR_ROLES))
GOVERNANCE_ROLE_TUPLE = tuple(sorted(GOVERNANCE_ROLES))


class SafetyRecordCreate(BaseModel):
    recordRef: str | None = None
    recordType: str
    domain: str
    confidentiality: str = "standard"
    reporterVisibility: str | None = None
    severity: str = "amber"
    title: str
    summary: str
    description: str = ""
    premisesRef: str = "default-premises"
    patientRef: str | None = None
    episodeRef: str | None = None
    affectedStaffSubject: str | None = None
    affectedStaffName: str | None = None
    sourceModule: str = "manual"
    sourceRecordRef: str | None = None
    immediateRisk: bool = False
    safetyHoldRequested: bool = False
    operationalImpact: dict[str, Any] = Field(default_factory=dict)
    protectiveSummary: str | None = None
    owners: dict[str, dict[str, str | None]] = Field(default_factory=dict)
    conflictSubjects: list[str] = Field(default_factory=list)
    dueAt: datetime | None = None
    links: list[dict[str, Any]] = Field(default_factory=list)


class TriagePayload(BaseModel):
    expectedVersion: int
    severity: str | None = None
    confidentiality: str | None = None
    status: str | None = None
    immediateRisk: bool | None = None
    safetyHoldRequested: bool | None = None
    operationalImpact: dict[str, Any] | None = None
    protectiveSummary: str | None = None
    dueAt: datetime | None = None
    reason: str


class OwnerAssignmentPayload(BaseModel):
    expectedVersion: int
    owners: dict[str, dict[str, str | None]]
    reason: str


class OwnershipDecisionPayload(BaseModel):
    expectedVersion: int
    decision: str
    reason: str


class ConflictPayload(BaseModel):
    expectedVersion: int
    subject: str
    reason: str


class SafetyActionCreate(BaseModel):
    actionRef: str | None = None
    actionType: str
    title: str
    description: str = ""
    owner: dict[str, str]
    dueAt: datetime | None = None
    requiresIndependentVerification: bool | None = None


class SafetyActionComplete(BaseModel):
    expectedVersion: int
    completionEvidence: str


class SafetyActionVerify(BaseModel):
    expectedVersion: int
    decision: str
    note: str


class EscalationCreate(BaseModel):
    escalationRef: str | None = None
    reason: str
    to: dict[str, str | None] = Field(default_factory=lambda: {"role": "governance_lead"})
    dueAt: datetime | None = None


class ClosureReviewPayload(BaseModel):
    decision: str
    reason: str


class ClosePayload(BaseModel):
    expectedVersion: int
    rootCause: str | None = None
    recurrenceControls: list[str] = Field(default_factory=list)
    reason: str


class ReopenPayload(BaseModel):
    expectedVersion: int
    reason: str


def _bundle(session: Session, record: SafetyRecordV25) -> dict[str, Any]:
    actions = session.exec(select(SafetyActionV25).where(SafetyActionV25.record_ref == record.record_ref).order_by(SafetyActionV25.created_at)).all()
    decisions = session.exec(select(SafetyDecisionV25).where(SafetyDecisionV25.record_ref == record.record_ref).order_by(SafetyDecisionV25.created_at.desc())).all()
    escalations = session.exec(select(SafetyEscalationV25).where(SafetyEscalationV25.record_ref == record.record_ref).order_by(SafetyEscalationV25.created_at.desc())).all()
    links = session.exec(select(SafetyLinkV25).where(SafetyLinkV25.record_ref == record.record_ref).order_by(SafetyLinkV25.created_at)).all()
    return {
        "record": sensitive_record_dict(record),
        "actions": [action_dict(item) for item in actions],
        "decisions": [decision_dict(item) for item in decisions],
        "escalations": [escalation_dict(item) for item in escalations],
        "links": [link_dict(item) for item in links],
        "closureGate": closure_gate(session, record),
    }


@router.get("/contracts")
def get_contracts(_: AuthContext = Depends(require_authenticated)) -> dict[str, Any]:
    return {
        "recordTypes": [
            "patient_safety", "near_miss", "staff_welfare", "conduct", "bullying", "harassment",
            "retaliation", "grievance", "complaint", "safeguarding", "operational_failure",
            "data_integrity", "privacy",
        ],
        "domains": ["patient", "staff", "mixed", "operations", "governance"],
        "confidentiality": sorted(CONFIDENTIALITY),
        "severities": sorted(SEVERITIES),
        "states": ["reported", "triaged", "protective_action", "investigation", "verification", "escalated", "stopped", "closed"],
        "principles": [
            "Any authenticated staff member may report a safety matter or immediate concern.",
            "Restricted staff details never appear on general hospital boards.",
            "Conflicted people cannot own, investigate, verify or close the matter.",
            "LucyWorks may request a safety hold and create accountable work; it does not diagnose, prescribe, acknowledge results, consent, admit or discharge.",
            "Red and critical matters require completed actions, independent verification, root cause, recurrence controls and independent closure approval.",
        ],
    }


@router.post("/records")
def post_record(
    payload: SafetyRecordCreate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    record, created = create_record(session, auth, payload.model_dump())
    session.commit()
    session.refresh(record)
    return {"created": created, **_bundle(session, record)}


@router.get("/records")
def list_records(
    status: str | None = None,
    severity: str | None = None,
    domain: str | None = None,
    patient_ref: str | None = None,
    episode_ref: str | None = None,
    limit: int = Query(default=250, ge=1, le=1000),
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    query = select(SafetyRecordV25).order_by(SafetyRecordV25.updated_at.desc())
    if status:
        query = query.where(SafetyRecordV25.status == status)
    if severity:
        query = query.where(SafetyRecordV25.severity == severity)
    if domain:
        query = query.where(SafetyRecordV25.domain == domain)
    if patient_ref:
        query = query.where(SafetyRecordV25.patient_ref == patient_ref)
    if episode_ref:
        query = query.where(SafetyRecordV25.episode_ref == episode_ref)
    rows = session.exec(query.limit(limit)).all()
    visible = [sensitive_record_dict(row) for row in rows if can_view(row, auth)]
    return {"records": visible, "count": len(visible), "hiddenRestrictedCount": len(rows) - len(visible)}


@router.get("/board-indicators")
def board_indicators(
    premises_ref: str | None = None,
    patient_ref: str | None = None,
    episode_ref: str | None = None,
    session: Session = Depends(get_session),
    _: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    query = select(SafetyRecordV25).where(SafetyRecordV25.status.in_(OPEN_RECORD_STATUSES)).order_by(SafetyRecordV25.updated_at.desc())
    if premises_ref:
        query = query.where(SafetyRecordV25.premises_ref == premises_ref)
    if patient_ref:
        query = query.where(SafetyRecordV25.patient_ref == patient_ref)
    if episode_ref:
        query = query.where(SafetyRecordV25.episode_ref == episode_ref)
    rows = session.exec(query).all()
    return {"indicators": [public_record_dict(row) for row in rows], "count": len(rows)}


@router.get("/records/{record_ref}")
def get_record(
    record_ref: str,
    reason: str | None = None,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    record = require_record(session, record_ref)
    if not can_view(record, auth):
        raise HTTPException(status_code=404, detail="safety record not found")
    record_access(session, record, auth, reason=reason)
    session.commit()
    return _bundle(session, record)


@router.patch("/records/{record_ref}/triage")
def triage_record(
    record_ref: str,
    payload: TriagePayload,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*SENIOR_ROLE_TUPLE)),
) -> dict[str, Any]:
    record = require_record(session, record_ref)
    if not can_view(record, auth) or is_conflicted(record, auth):
        raise HTTPException(status_code=403, detail="actor is not permitted to triage this record")
    require_expected_version(record.version, payload.expectedVersion)
    before = sensitive_record_dict(record)
    updates = payload.model_dump(exclude_unset=True)
    if payload.severity is not None:
        value = payload.severity.lower().strip()
        if value not in SEVERITIES:
            raise HTTPException(status_code=400, detail="invalid severity")
        record.severity = value
    if payload.confidentiality is not None:
        value = payload.confidentiality.lower().strip()
        if value not in CONFIDENTIALITY:
            raise HTTPException(status_code=400, detail="invalid confidentiality")
        if record.record_type in {"conduct", "bullying", "harassment", "retaliation", "grievance"} and value != "strict":
            raise HTTPException(status_code=409, detail="staff conduct and grievance records must remain strict")
        record.confidentiality = value
    if payload.status is not None:
        value = payload.status.lower().strip()
        if value not in OPEN_RECORD_STATUSES:
            raise HTTPException(status_code=400, detail="triage cannot close a record")
        record.status = value
    if "immediateRisk" in updates:
        record.immediate_risk = bool(payload.immediateRisk)
    if "safetyHoldRequested" in updates:
        record.safety_hold_requested = bool(payload.safetyHoldRequested)
    if payload.operationalImpact is not None:
        record.operational_impact = payload.operationalImpact
    if "protectiveSummary" in updates:
        record.protective_summary = payload.protectiveSummary
    if "dueAt" in updates:
        record.due_at = payload.dueAt
    if record.severity in {"red", "critical"}:
        record.immediate_risk = True
        if record.status in {"reported", "triaged"}:
            record.status = "protective_action"
    record.version += 1
    record.updated_at = utc_now()
    session.add(record)
    decision = create_decision(
        session, record, auth,
        decision_type="triage", decision=record.status, reason=payload.reason,
        previous_state=before, result_state=sensitive_record_dict(record),
    )
    session.commit()
    return {"decision": decision_dict(decision), **_bundle(session, record)}


@router.post("/records/{record_ref}/owners")
def put_owners(
    record_ref: str,
    payload: OwnerAssignmentPayload,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*SENIOR_ROLE_TUPLE)),
) -> dict[str, Any]:
    record = require_record(session, record_ref)
    decision = assign_owners(session, record, auth, payload.model_dump())
    session.commit()
    return {"decision": decision_dict(decision), **_bundle(session, record)}


@router.post("/records/{record_ref}/ownership-decision")
def ownership_decision(
    record_ref: str,
    payload: OwnershipDecisionPayload,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    record = require_record(session, record_ref)
    if not can_view(record, auth):
        raise HTTPException(status_code=404, detail="safety record not found")
    require_expected_version(record.version, payload.expectedVersion)
    owner_fields = []
    if auth.subject == record.accountable_owner_subject:
        owner_fields.append("accountable")
    if auth.subject == record.clinical_owner_subject:
        owner_fields.append("clinical")
    if auth.subject == record.independent_owner_subject:
        owner_fields.append("independent")
    if not owner_fields:
        raise HTTPException(status_code=403, detail="only a named owner may accept or reject ownership")
    decision_value = payload.decision.lower().strip()
    if decision_value not in {"accepted", "rejected"}:
        raise HTTPException(status_code=400, detail="decision must be accepted or rejected")
    before = sensitive_record_dict(record)
    if decision_value == "rejected":
        for owner_type in owner_fields:
            setattr(record, f"{owner_type}_owner_subject", None)
            setattr(record, f"{owner_type}_owner_name", None)
            setattr(record, f"{owner_type}_owner_role", None)
        record.status = "escalated"
        record.escalated_at = utc_now()
    record.version += 1
    record.updated_at = utc_now()
    session.add(record)
    decision = create_decision(
        session, record, auth,
        decision_type="ownership_response", decision=decision_value, reason=payload.reason,
        previous_state=before, result_state=sensitive_record_dict(record),
    )
    escalation = None
    if decision_value == "rejected":
        escalation = create_escalation(session, record, auth, {"reason": f"Named owner rejected responsibility: {payload.reason}", "to": {"role": "governance_lead"}})
    session.commit()
    return {"decision": decision_dict(decision), "escalation": escalation_dict(escalation) if escalation else None, **_bundle(session, record)}


@router.post("/records/{record_ref}/conflicts")
def declare_conflict(
    record_ref: str,
    payload: ConflictPayload,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*SENIOR_ROLE_TUPLE)),
) -> dict[str, Any]:
    record = require_record(session, record_ref)
    require_expected_version(record.version, payload.expectedVersion)
    before = sensitive_record_dict(record)
    conflicts = list(record.conflict_subjects or [])
    if payload.subject not in conflicts:
        conflicts.append(payload.subject)
    record.conflict_subjects = conflicts
    for owner_type in ("accountable", "clinical", "independent"):
        if getattr(record, f"{owner_type}_owner_subject") == payload.subject:
            setattr(record, f"{owner_type}_owner_subject", None)
            setattr(record, f"{owner_type}_owner_name", None)
            setattr(record, f"{owner_type}_owner_role", None)
    record.status = "escalated"
    record.escalated_at = utc_now()
    record.version += 1
    record.updated_at = utc_now()
    session.add(record)
    decision = create_decision(
        session, record, auth,
        decision_type="conflict", decision="declared", reason=payload.reason,
        previous_state=before, result_state=sensitive_record_dict(record),
    )
    escalation = create_escalation(session, record, auth, {"reason": f"Conflict declared: {payload.reason}", "to": {"role": "governance_lead"}})
    session.commit()
    return {"decision": decision_dict(decision), "escalation": escalation_dict(escalation), **_bundle(session, record)}


@router.post("/records/{record_ref}/actions")
def post_action(
    record_ref: str,
    payload: SafetyActionCreate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    record = require_record(session, record_ref)
    if not can_view(record, auth):
        raise HTTPException(status_code=404, detail="safety record not found")
    data = payload.model_dump()
    if payload.requiresIndependentVerification is None:
        data.pop("requiresIndependentVerification", None)
    action = create_action(session, record, auth, data)
    session.commit()
    session.refresh(action)
    return {"action": action_dict(action), **_bundle(session, record)}


@router.patch("/records/{record_ref}/actions/{action_ref}/complete")
def patch_action_complete(
    record_ref: str,
    action_ref: str,
    payload: SafetyActionComplete,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    record = require_record(session, record_ref)
    if not can_view(record, auth):
        raise HTTPException(status_code=404, detail="safety record not found")
    action = require_action(session, record_ref, action_ref)
    decision = complete_action(session, record, action, auth, payload.model_dump())
    session.commit()
    return {"decision": decision_dict(decision), "action": action_dict(action), **_bundle(session, record)}


@router.patch("/records/{record_ref}/actions/{action_ref}/verify")
def patch_action_verify(
    record_ref: str,
    action_ref: str,
    payload: SafetyActionVerify,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    record = require_record(session, record_ref)
    if not can_view(record, auth):
        raise HTTPException(status_code=404, detail="safety record not found")
    action = require_action(session, record_ref, action_ref)
    decision = verify_action(session, record, action, auth, payload.model_dump())
    session.commit()
    return {"decision": decision_dict(decision), "action": action_dict(action), **_bundle(session, record)}


@router.post("/records/{record_ref}/escalations")
def post_escalation(
    record_ref: str,
    payload: EscalationCreate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    record = require_record(session, record_ref)
    if not can_view(record, auth):
        raise HTTPException(status_code=404, detail="safety record not found")
    escalation = create_escalation(session, record, auth, payload.model_dump())
    session.commit()
    return {"escalation": escalation_dict(escalation), **_bundle(session, record)}


@router.post("/evaluate-overdue")
def post_evaluate_overdue(
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*SENIOR_ROLE_TUPLE)),
) -> dict[str, Any]:
    rows = evaluate_overdue(session, auth)
    session.commit()
    return {"created": [escalation_dict(row) for row in rows], "count": len(rows)}


@router.post("/records/{record_ref}/closure-review")
def post_closure_review(
    record_ref: str,
    payload: ClosureReviewPayload,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    record = require_record(session, record_ref)
    if not can_view(record, auth):
        raise HTTPException(status_code=404, detail="safety record not found")
    decision = review_closure(session, record, auth, payload.model_dump())
    session.commit()
    return {"decision": decision_dict(decision), **_bundle(session, record)}


@router.post("/records/{record_ref}/close")
def post_close_record(
    record_ref: str,
    payload: ClosePayload,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*SENIOR_ROLE_TUPLE)),
) -> dict[str, Any]:
    record = require_record(session, record_ref)
    if not can_view(record, auth):
        raise HTTPException(status_code=404, detail="safety record not found")
    decision = close_record(session, record, auth, payload.model_dump())
    session.commit()
    return {"decision": decision_dict(decision), **_bundle(session, record)}


@router.post("/records/{record_ref}/reopen")
def post_reopen_record(
    record_ref: str,
    payload: ReopenPayload,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*SENIOR_ROLE_TUPLE)),
) -> dict[str, Any]:
    record = require_record(session, record_ref)
    if not can_view(record, auth):
        raise HTTPException(status_code=404, detail="safety record not found")
    decision = reopen_record(session, record, auth, payload.model_dump())
    session.commit()
    return {"decision": decision_dict(decision), **_bundle(session, record)}


@router.get("/dashboard")
def get_dashboard(
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*SENIOR_ROLE_TUPLE)),
) -> dict[str, Any]:
    rows = session.exec(select(SafetyRecordV25).order_by(SafetyRecordV25.updated_at.desc())).all()
    visible = [row for row in rows if can_view(row, auth)]
    open_rows = [row for row in visible if row.status in OPEN_RECORD_STATUSES]
    return {
        "counts": {
            "visible": len(visible),
            "open": len(open_rows),
            "redOrCritical": sum(1 for row in open_rows if row.severity in {"red", "critical"}),
            "safetyHolds": sum(1 for row in open_rows if row.safety_hold_requested),
            "restricted": sum(1 for row in open_rows if row.confidentiality != "standard"),
            "unowned": sum(1 for row in open_rows if not (row.accountable_owner_subject or row.clinical_owner_subject or row.independent_owner_subject)),
        },
        "records": [public_record_dict(row) if row.confidentiality != "standard" else sensitive_record_dict(row) for row in open_rows[:100]],
    }


@router.get("/records/{record_ref}/access-log")
def get_access_log(
    record_ref: str,
    session: Session = Depends(get_session),
    _: AuthContext = Depends(require_roles(*GOVERNANCE_ROLE_TUPLE)),
) -> dict[str, Any]:
    require_record(session, record_ref)
    rows = session.exec(select(SafetyAccessEventV25).where(SafetyAccessEventV25.record_ref == record_ref).order_by(SafetyAccessEventV25.created_at.desc())).all()
    return {
        "recordRef": record_ref,
        "accessEvents": [
            {
                "accessRef": row.access_ref,
                "accessType": row.access_type,
                "reason": row.reason,
                "actor": {"subject": row.actor_subject, "name": row.actor_name, "role": row.actor_role, "authSource": row.actor_auth_source},
                "createdAt": row.created_at.isoformat(),
            }
            for row in rows
        ],
        "count": len(rows),
    }
