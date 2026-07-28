from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import HTTPException
from sqlmodel import Session, select

from app.auth import AuthContext
from app.evidence_service import create_evidence_event
from app.models import WorkItem
from app.safety_control_v25_models import (
    SafetyAccessEventV25,
    SafetyActionV25,
    SafetyDecisionV25,
    SafetyEscalationV25,
    SafetyLinkV25,
    SafetyRecordV25,
)

GOVERNANCE_ROLES = {"admin", "governance_lead", "hospital_director"}
SENIOR_ROLES = GOVERNANCE_ROLES | {"clinical_director", "ops_manager", "senior_clinician", "supervisor"}
CLINICAL_ROLES = {"clinician", "clinical_director", "nurse", "senior_clinician", "supervisor"}
OPERATIONAL_ROLES = {"hospital_director", "ops_manager", "supervisor"}

RECORD_TYPES = {
    "patient_safety",
    "near_miss",
    "staff_welfare",
    "conduct",
    "bullying",
    "harassment",
    "retaliation",
    "grievance",
    "complaint",
    "safeguarding",
    "operational_failure",
    "data_integrity",
    "privacy",
}
DOMAINS = {"patient", "staff", "mixed", "operations", "governance"}
CONFIDENTIALITY = {"standard", "restricted", "strict"}
SEVERITIES = {"green", "amber", "red", "critical"}
OPEN_RECORD_STATUSES = {"reported", "triaged", "protective_action", "investigation", "verification", "escalated", "stopped"}
ACTION_TYPES = {"protective", "clinical_review", "operational", "communication", "investigation", "corrective", "monitoring", "welfare_support"}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_ref(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _conflicts(record: SafetyRecordV25) -> set[str]:
    return {str(item) for item in (record.conflict_subjects or []) if item}


def is_conflicted(record: SafetyRecordV25, auth: AuthContext) -> bool:
    return auth.subject in _conflicts(record) and auth.role not in {"admin", "hospital_director"}


def is_named_party(record: SafetyRecordV25, auth: AuthContext) -> bool:
    return auth.subject in {
        record.created_by_subject,
        record.accountable_owner_subject,
        record.clinical_owner_subject,
        record.independent_owner_subject,
        record.affected_staff_subject,
    }


def can_view(record: SafetyRecordV25, auth: AuthContext) -> bool:
    if is_conflicted(record, auth):
        return False
    if record.confidentiality == "standard":
        return auth.verified
    if auth.role in GOVERNANCE_ROLES or is_named_party(record, auth):
        return True
    if record.confidentiality == "restricted" and record.domain in {"patient", "mixed"} and auth.role in {"clinical_director", "senior_clinician", "supervisor"}:
        return True
    return False


def can_manage(record: SafetyRecordV25, auth: AuthContext) -> bool:
    if not can_view(record, auth):
        return False
    return auth.role in SENIOR_ROLES or auth.subject in {
        record.accountable_owner_subject,
        record.clinical_owner_subject,
        record.independent_owner_subject,
    }


def sensitive_record_dict(record: SafetyRecordV25) -> dict[str, Any]:
    return {
        "id": record.id,
        "recordRef": record.record_ref,
        "recordType": record.record_type,
        "domain": record.domain,
        "confidentiality": record.confidentiality,
        "reporterVisibility": record.reporter_visibility,
        "severity": record.severity,
        "status": record.status,
        "title": record.title,
        "summary": record.summary,
        "description": record.description,
        "premisesRef": record.premises_ref,
        "patientRef": record.patient_ref,
        "episodeRef": record.episode_ref,
        "affectedStaffSubject": record.affected_staff_subject,
        "affectedStaffName": record.affected_staff_name,
        "sourceModule": record.source_module,
        "sourceRecordRef": record.source_record_ref,
        "immediateRisk": record.immediate_risk,
        "safetyHoldRequested": record.safety_hold_requested,
        "operationalImpact": record.operational_impact or {},
        "protectiveSummary": record.protective_summary,
        "accountableOwner": {
            "subject": record.accountable_owner_subject,
            "name": record.accountable_owner_name,
            "role": record.accountable_owner_role,
        },
        "clinicalOwner": {
            "subject": record.clinical_owner_subject,
            "name": record.clinical_owner_name,
            "role": record.clinical_owner_role,
        },
        "independentOwner": {
            "subject": record.independent_owner_subject,
            "name": record.independent_owner_name,
            "role": record.independent_owner_role,
        },
        "conflictSubjects": record.conflict_subjects or [],
        "rootCause": record.root_cause,
        "recurrenceControls": record.recurrence_controls or [],
        "dueAt": _iso(record.due_at),
        "escalatedAt": _iso(record.escalated_at),
        "closedAt": _iso(record.closed_at),
        "version": record.version,
        "evidenceEventRef": record.evidence_event_ref,
        "createdBy": {
            "subject": record.created_by_subject,
            "name": record.created_by_name,
            "role": record.created_by_role,
        },
        "createdAt": _iso(record.created_at),
        "updatedAt": _iso(record.updated_at),
    }


def public_record_dict(record: SafetyRecordV25) -> dict[str, Any]:
    restricted = record.confidentiality != "standard"
    return {
        "recordRef": record.record_ref,
        "recordType": "restricted_safety_matter" if restricted and record.domain == "staff" else record.record_type,
        "domain": record.domain,
        "confidentiality": record.confidentiality,
        "severity": record.severity,
        "status": record.status,
        "title": "Restricted safety matter" if restricted else record.title,
        "summary": record.protective_summary or ("Restricted details — contact the named safety owner" if restricted else record.summary),
        "premisesRef": record.premises_ref,
        "patientRef": record.patient_ref if record.domain in {"patient", "mixed"} else None,
        "episodeRef": record.episode_ref if record.domain in {"patient", "mixed"} else None,
        "immediateRisk": record.immediate_risk,
        "safetyHoldRequested": record.safety_hold_requested,
        "operationalImpact": record.operational_impact or {},
        "ownerRole": record.clinical_owner_role or record.accountable_owner_role or record.independent_owner_role,
        "dueAt": _iso(record.due_at),
        "updatedAt": _iso(record.updated_at),
    }


def action_dict(action: SafetyActionV25) -> dict[str, Any]:
    return {
        "id": action.id,
        "actionRef": action.action_ref,
        "recordRef": action.record_ref,
        "actionType": action.action_type,
        "title": action.title,
        "description": action.description,
        "owner": {"subject": action.owner_subject, "name": action.owner_name, "role": action.owner_role},
        "status": action.status,
        "dueAt": _iso(action.due_at),
        "completionEvidence": action.completion_evidence,
        "completedAt": _iso(action.completed_at),
        "requiresIndependentVerification": action.requires_independent_verification,
        "verificationStatus": action.verification_status,
        "verifiedBy": {
            "subject": action.verified_by_subject,
            "name": action.verified_by_name,
            "role": action.verified_by_role,
        },
        "verificationNote": action.verification_note,
        "verifiedAt": _iso(action.verified_at),
        "workItemId": action.work_item_id,
        "version": action.version,
        "evidenceEventRef": action.evidence_event_ref,
        "createdAt": _iso(action.created_at),
        "updatedAt": _iso(action.updated_at),
    }


def decision_dict(decision: SafetyDecisionV25) -> dict[str, Any]:
    return {
        "decisionRef": decision.decision_ref,
        "recordRef": decision.record_ref,
        "decisionType": decision.decision_type,
        "decision": decision.decision,
        "reason": decision.reason,
        "previousState": decision.previous_state or {},
        "resultState": decision.result_state or {},
        "actor": {"subject": decision.actor_subject, "name": decision.actor_name, "role": decision.actor_role},
        "evidenceEventRef": decision.evidence_event_ref,
        "createdAt": _iso(decision.created_at),
    }


def escalation_dict(row: SafetyEscalationV25) -> dict[str, Any]:
    return {
        "escalationRef": row.escalation_ref,
        "recordRef": row.record_ref,
        "reason": row.reason,
        "fromSubject": row.from_subject,
        "fromRole": row.from_role,
        "toSubject": row.to_subject,
        "toRole": row.to_role,
        "status": row.status,
        "dueAt": _iso(row.due_at),
        "resolvedAt": _iso(row.resolved_at),
        "resolutionNote": row.resolution_note,
        "actor": {"subject": row.actor_subject, "name": row.actor_name, "role": row.actor_role},
        "evidenceEventRef": row.evidence_event_ref,
        "createdAt": _iso(row.created_at),
    }


def link_dict(row: SafetyLinkV25) -> dict[str, Any]:
    return {
        "linkRef": row.link_ref,
        "recordRef": row.record_ref,
        "entityType": row.entity_type,
        "entityRef": row.entity_ref,
        "relationship": row.relationship,
        "visibility": row.visibility,
        "createdAt": _iso(row.created_at),
    }


def require_record(session: Session, record_ref: str) -> SafetyRecordV25:
    row = session.exec(select(SafetyRecordV25).where(SafetyRecordV25.record_ref == record_ref)).first()
    if not row:
        raise HTTPException(status_code=404, detail="safety record not found")
    return row


def require_action(session: Session, record_ref: str, action_ref: str) -> SafetyActionV25:
    row = session.exec(
        select(SafetyActionV25).where(SafetyActionV25.record_ref == record_ref, SafetyActionV25.action_ref == action_ref)
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="safety action not found")
    return row


def require_expected_version(actual: int, expected: int, code: str = "stale_safety_record") -> None:
    if actual != expected:
        raise HTTPException(status_code=409, detail={"code": code, "expectedVersion": actual, "suppliedVersion": expected})


def record_access(session: Session, record: SafetyRecordV25, auth: AuthContext, access_type: str = "view", reason: str | None = None) -> None:
    if record.confidentiality == "standard":
        return
    session.add(SafetyAccessEventV25(
        access_ref=new_ref("safety-access"),
        record_ref=record.record_ref,
        access_type=access_type,
        reason=reason,
        actor_subject=auth.subject,
        actor_name=auth.actor_name,
        actor_role=auth.role,
        actor_auth_source=auth.auth_source,
    ))


def create_decision(
    session: Session,
    record: SafetyRecordV25,
    auth: AuthContext,
    *,
    decision_type: str,
    decision: str,
    reason: str,
    previous_state: dict[str, Any] | None = None,
    result_state: dict[str, Any] | None = None,
) -> SafetyDecisionV25:
    row = SafetyDecisionV25(
        decision_ref=new_ref("safety-decision"),
        record_ref=record.record_ref,
        decision_type=decision_type,
        decision=decision,
        reason=reason,
        previous_state=previous_state or {},
        result_state=result_state or {},
        actor_subject=auth.subject,
        actor_name=auth.actor_name,
        actor_role=auth.role,
        actor_auth_source=auth.auth_source,
    )
    session.add(row)
    session.flush()
    event, _ = create_evidence_event(
        session,
        event_type=f"safety_{decision_type}",
        action=f"safety {decision_type}: {decision}",
        patient_case_id=record.patient_ref,
        referral_episode_id=record.episode_ref,
        actor_id=auth.actor_id or auth.subject,
        actor_name=auth.actor_name,
        actor_role=auth.role,
        actor_auth_source=auth.auth_source,
        previous_state=previous_state,
        new_state=result_state,
        reason=reason,
        compliance_domain="clinical_governance" if record.domain in {"patient", "mixed"} else "workforce_governance",
        risk_level=record.severity,
        source_module="safety-control-v25",
        source_record_ref=record.record_ref,
        causation_event_ref=record.evidence_event_ref,
        entity_type="safety_record",
        entity_id=record.record_ref,
        idempotency_key=f"safety:{record.record_ref}:{decision_type}:{row.decision_ref}",
    )
    row.evidence_event_ref = event.event_ref
    session.add(row)
    return row


def _new_work_item(session: Session, record: SafetyRecordV25, *, title: str, description: str, urgency: str, owner_role: str, owner_user_id: int | None = None, due_at: datetime | None = None) -> WorkItem:
    item = WorkItem(
        title=title,
        input_type="safety_control_v25",
        source="safety-control-v25",
        category=record.record_type,
        description=description,
        urgency=urgency,
        owner_role=owner_role,
        owner_user_id=owner_user_id,
        linked_episode_ref=record.episode_ref,
        linked_patient_name=record.patient_ref,
        status="new",
        due_at=due_at,
    )
    session.add(item)
    session.flush()
    return item


def create_record(session: Session, auth: AuthContext, data: dict[str, Any]) -> tuple[SafetyRecordV25, bool]:
    record_type = str(data.get("recordType") or "").strip().lower()
    domain = str(data.get("domain") or "").strip().lower()
    severity = str(data.get("severity") or "amber").strip().lower()
    confidentiality = str(data.get("confidentiality") or "standard").strip().lower()
    if record_type not in RECORD_TYPES:
        raise HTTPException(status_code=400, detail=f"recordType must be one of: {', '.join(sorted(RECORD_TYPES))}")
    if domain not in DOMAINS:
        raise HTTPException(status_code=400, detail=f"domain must be one of: {', '.join(sorted(DOMAINS))}")
    if severity not in SEVERITIES:
        raise HTTPException(status_code=400, detail=f"severity must be one of: {', '.join(sorted(SEVERITIES))}")
    if confidentiality not in CONFIDENTIALITY:
        raise HTTPException(status_code=400, detail=f"confidentiality must be one of: {', '.join(sorted(CONFIDENTIALITY))}")
    if record_type in {"conduct", "bullying", "harassment", "retaliation", "grievance"}:
        confidentiality = "strict"
        domain = "staff" if domain == "operations" else domain

    source_module = str(data.get("sourceModule") or "manual")
    source_record_ref = data.get("sourceRecordRef")
    if source_record_ref:
        existing = session.exec(
            select(SafetyRecordV25).where(
                SafetyRecordV25.source_module == source_module,
                SafetyRecordV25.source_record_ref == str(source_record_ref),
            )
        ).first()
        if existing:
            return existing, False

    conflict_subjects = [str(item) for item in (data.get("conflictSubjects") or []) if item]
    owners = data.get("owners") or {}
    accountable = owners.get("accountable") or {}
    clinical = owners.get("clinical") or {}
    independent = owners.get("independent") or {}
    for owner in (accountable, clinical, independent):
        if owner.get("subject") and str(owner.get("subject")) in conflict_subjects:
            raise HTTPException(status_code=409, detail={"code": "conflicted_owner", "subject": owner.get("subject")})

    immediate = bool(data.get("immediateRisk")) or severity in {"red", "critical"}
    record = SafetyRecordV25(
        record_ref=str(data.get("recordRef") or new_ref("safety")),
        record_type=record_type,
        domain=domain,
        confidentiality=confidentiality,
        reporter_visibility=str(data.get("reporterVisibility") or ("protected" if confidentiality != "standard" else "named")),
        severity=severity,
        status="protective_action" if immediate else "reported",
        title=str(data.get("title") or "Safety matter").strip(),
        summary=str(data.get("summary") or "").strip(),
        description=str(data.get("description") or "").strip(),
        premises_ref=str(data.get("premisesRef") or "default-premises"),
        patient_ref=data.get("patientRef"),
        episode_ref=data.get("episodeRef"),
        affected_staff_subject=data.get("affectedStaffSubject"),
        affected_staff_name=data.get("affectedStaffName"),
        source_module=source_module,
        source_record_ref=str(source_record_ref) if source_record_ref else None,
        immediate_risk=immediate,
        safety_hold_requested=bool(data.get("safetyHoldRequested")) or severity == "critical",
        operational_impact=data.get("operationalImpact") or {},
        protective_summary=data.get("protectiveSummary"),
        accountable_owner_subject=accountable.get("subject"),
        accountable_owner_name=accountable.get("name"),
        accountable_owner_role=accountable.get("role"),
        clinical_owner_subject=clinical.get("subject"),
        clinical_owner_name=clinical.get("name"),
        clinical_owner_role=clinical.get("role"),
        independent_owner_subject=independent.get("subject"),
        independent_owner_name=independent.get("name"),
        independent_owner_role=independent.get("role"),
        conflict_subjects=conflict_subjects,
        due_at=data.get("dueAt"),
        created_by_subject=auth.subject,
        created_by_name=auth.actor_name,
        created_by_role=auth.role,
        created_by_auth_source=auth.auth_source,
    )
    if not record.summary:
        raise HTTPException(status_code=400, detail="summary is required")
    session.add(record)
    session.flush()

    event, _ = create_evidence_event(
        session,
        event_type="safety_record_created",
        action="cross-system safety record created",
        patient_case_id=record.patient_ref,
        referral_episode_id=record.episode_ref,
        actor_id=auth.actor_id or auth.subject,
        actor_name=auth.actor_name,
        actor_role=auth.role,
        actor_auth_source=auth.auth_source,
        new_state=sensitive_record_dict(record),
        reason=record.summary,
        supervisor_required=severity in {"red", "critical"},
        supervisor_approval_status="pending" if severity in {"red", "critical"} else "not_required",
        compliance_domain="clinical_governance" if domain in {"patient", "mixed"} else "workforce_governance",
        risk_level=severity,
        source_module="safety-control-v25",
        source_record_ref=record.record_ref,
        entity_type="safety_record",
        entity_id=record.record_ref,
        idempotency_key=f"safety:create:{record.record_ref}",
    )
    record.evidence_event_ref = event.event_ref
    session.add(record)

    links = list(data.get("links") or [])
    if record.patient_ref:
        links.append({"entityType": "patient", "entityRef": record.patient_ref, "relationship": "affected_patient", "visibility": "standard"})
    if record.episode_ref:
        links.append({"entityType": "episode", "entityRef": record.episode_ref, "relationship": "affected_episode", "visibility": "standard"})
    if record.affected_staff_subject:
        links.append({"entityType": "staff", "entityRef": record.affected_staff_subject, "relationship": "affected_staff", "visibility": "restricted"})
    seen: set[tuple[str, str, str]] = set()
    for link in links:
        key = (str(link.get("entityType")), str(link.get("entityRef")), str(link.get("relationship") or "related"))
        if not key[0] or not key[1] or key in seen:
            continue
        seen.add(key)
        session.add(SafetyLinkV25(
            link_ref=new_ref("safety-link"),
            record_ref=record.record_ref,
            entity_type=key[0],
            entity_ref=key[1],
            relationship=key[2],
            visibility=str(link.get("visibility") or ("restricted" if confidentiality != "standard" else "standard")),
            created_by_subject=auth.subject,
        ))

    owner_role = record.clinical_owner_role or record.accountable_owner_role or record.independent_owner_role
    if owner_role:
        _new_work_item(
            session,
            record,
            title=f"Safety response: {record.title}",
            description=record.protective_summary or record.summary,
            urgency=record.severity,
            owner_role=owner_role,
            due_at=record.due_at,
        )
    return record, True


def assign_owners(session: Session, record: SafetyRecordV25, auth: AuthContext, data: dict[str, Any]) -> SafetyDecisionV25:
    if auth.role not in SENIOR_ROLES:
        raise HTTPException(status_code=403, detail="senior role required to assign safety ownership")
    if is_conflicted(record, auth):
        raise HTTPException(status_code=403, detail={"code": "conflicted_actor_cannot_assign"})
    expected = int(data.get("expectedVersion"))
    require_expected_version(record.version, expected)
    before = sensitive_record_dict(record)
    conflicts = _conflicts(record)
    for key, prefix in (("accountable", "accountable_owner"), ("clinical", "clinical_owner"), ("independent", "independent_owner")):
        owner = (data.get("owners") or {}).get(key)
        if owner is None:
            continue
        subject = owner.get("subject")
        if subject and str(subject) in conflicts:
            raise HTTPException(status_code=409, detail={"code": "conflicted_owner", "subject": subject})
        setattr(record, f"{prefix}_subject", subject)
        setattr(record, f"{prefix}_name", owner.get("name"))
        setattr(record, f"{prefix}_role", owner.get("role"))
    record.status = "triaged" if record.status == "reported" else record.status
    record.version += 1
    record.updated_at = utc_now()
    session.add(record)
    after = sensitive_record_dict(record)
    return create_decision(
        session,
        record,
        auth,
        decision_type="ownership",
        decision="assigned",
        reason=str(data.get("reason") or "named safety ownership assigned"),
        previous_state=before,
        result_state=after,
    )


def create_action(session: Session, record: SafetyRecordV25, auth: AuthContext, data: dict[str, Any]) -> SafetyActionV25:
    if not can_manage(record, auth) and str(data.get("actionType")) not in {"protective", "welfare_support", "communication"}:
        raise HTTPException(status_code=403, detail="record owner or senior role required")
    action_type = str(data.get("actionType") or "").strip().lower()
    if action_type not in ACTION_TYPES:
        raise HTTPException(status_code=400, detail=f"actionType must be one of: {', '.join(sorted(ACTION_TYPES))}")
    owner = data.get("owner") or {}
    if not owner.get("subject") or not owner.get("name") or not owner.get("role"):
        raise HTTPException(status_code=400, detail="action requires a named owner subject, name and role")
    if str(owner.get("subject")) in _conflicts(record):
        raise HTTPException(status_code=409, detail={"code": "conflicted_action_owner", "subject": owner.get("subject")})
    action = SafetyActionV25(
        action_ref=str(data.get("actionRef") or new_ref("safety-action")),
        record_ref=record.record_ref,
        action_type=action_type,
        title=str(data.get("title") or "Safety action").strip(),
        description=str(data.get("description") or "").strip(),
        owner_subject=str(owner.get("subject")),
        owner_name=str(owner.get("name")),
        owner_role=str(owner.get("role")),
        due_at=data.get("dueAt"),
        requires_independent_verification=bool(data.get("requiresIndependentVerification", record.severity in {"red", "critical"} or action_type in {"protective", "corrective"})),
        created_by_subject=auth.subject,
    )
    session.add(action)
    session.flush()
    item = _new_work_item(
        session,
        record,
        title=action.title,
        description=action.description or record.protective_summary or record.summary,
        urgency=record.severity,
        owner_role=action.owner_role,
        due_at=action.due_at,
    )
    action.work_item_id = item.id
    event, _ = create_evidence_event(
        session,
        event_type="safety_action_created",
        action=f"safety action created: {action.action_type}",
        patient_case_id=record.patient_ref,
        referral_episode_id=record.episode_ref,
        actor_id=auth.actor_id or auth.subject,
        actor_name=auth.actor_name,
        actor_role=auth.role,
        actor_auth_source=auth.auth_source,
        new_state=action_dict(action),
        reason=action.title,
        compliance_domain="clinical_governance" if record.domain in {"patient", "mixed"} else "workforce_governance",
        risk_level=record.severity,
        source_module="safety-control-v25",
        source_record_ref=action.action_ref,
        causation_event_ref=record.evidence_event_ref,
        entity_type="safety_action",
        entity_id=action.action_ref,
        idempotency_key=f"safety-action:create:{action.action_ref}",
    )
    action.evidence_event_ref = event.event_ref
    session.add(action)
    if record.status in {"reported", "triaged"} and action_type == "protective":
        record.status = "protective_action"
        record.version += 1
        record.updated_at = utc_now()
        session.add(record)
    return action


def complete_action(session: Session, record: SafetyRecordV25, action: SafetyActionV25, auth: AuthContext, data: dict[str, Any]) -> SafetyDecisionV25:
    require_expected_version(action.version, int(data.get("expectedVersion")), "stale_safety_action")
    if auth.subject != action.owner_subject and auth.role not in SENIOR_ROLES:
        raise HTTPException(status_code=403, detail="action owner or senior role required")
    evidence = str(data.get("completionEvidence") or "").strip()
    if len(evidence) < 8:
        raise HTTPException(status_code=400, detail="completionEvidence must explain what was done")
    before = action_dict(action)
    action.status = "completed"
    action.completion_evidence = evidence
    action.completed_at = utc_now()
    action.verification_status = "pending" if action.requires_independent_verification else "not_required"
    action.version += 1
    action.updated_at = utc_now()
    session.add(action)
    if action.work_item_id:
        item = session.get(WorkItem, action.work_item_id)
        if item:
            item.status = "completed"
            item.updated_at = utc_now()
            session.add(item)
    after = action_dict(action)
    return create_decision(
        session,
        record,
        auth,
        decision_type="action_completion",
        decision="completed",
        reason=evidence,
        previous_state=before,
        result_state=after,
    )


def verify_action(session: Session, record: SafetyRecordV25, action: SafetyActionV25, auth: AuthContext, data: dict[str, Any]) -> SafetyDecisionV25:
    require_expected_version(action.version, int(data.get("expectedVersion")), "stale_safety_action")
    if action.status != "completed":
        raise HTTPException(status_code=409, detail="action must be completed before verification")
    if auth.subject == action.owner_subject:
        raise HTTPException(status_code=409, detail={"code": "independent_verifier_required"})
    if auth.role not in SENIOR_ROLES and auth.subject != record.independent_owner_subject:
        raise HTTPException(status_code=403, detail="independent owner or senior role required")
    decision = str(data.get("decision") or "").lower().strip()
    if decision not in {"verified", "rejected"}:
        raise HTTPException(status_code=400, detail="decision must be verified or rejected")
    note = str(data.get("note") or "").strip()
    if len(note) < 8:
        raise HTTPException(status_code=400, detail="verification note is required")
    before = action_dict(action)
    action.verification_status = decision
    action.verified_by_subject = auth.subject
    action.verified_by_name = auth.actor_name
    action.verified_by_role = auth.role
    action.verification_note = note
    action.verified_at = utc_now()
    if decision == "rejected":
        action.status = "open"
        action.completed_at = None
    action.version += 1
    action.updated_at = utc_now()
    session.add(action)
    after = action_dict(action)
    return create_decision(
        session,
        record,
        auth,
        decision_type="action_verification",
        decision=decision,
        reason=note,
        previous_state=before,
        result_state=after,
    )


def create_escalation(session: Session, record: SafetyRecordV25, auth: AuthContext, data: dict[str, Any]) -> SafetyEscalationV25:
    if not can_manage(record, auth) and auth.role not in SENIOR_ROLES:
        raise HTTPException(status_code=403, detail="record owner or senior role required")
    target = data.get("to") or {}
    to_role = str(target.get("role") or "governance_lead")
    if target.get("subject") and str(target.get("subject")) in _conflicts(record):
        raise HTTPException(status_code=409, detail={"code": "conflicted_escalation_target"})
    row = SafetyEscalationV25(
        escalation_ref=str(data.get("escalationRef") or new_ref("safety-escalation")),
        record_ref=record.record_ref,
        reason=str(data.get("reason") or "safety matter escalated").strip(),
        from_subject=record.accountable_owner_subject,
        from_role=record.accountable_owner_role,
        to_subject=target.get("subject"),
        to_role=to_role,
        due_at=data.get("dueAt"),
        actor_subject=auth.subject,
        actor_name=auth.actor_name,
        actor_role=auth.role,
    )
    session.add(row)
    session.flush()
    event, _ = create_evidence_event(
        session,
        event_type="safety_escalated",
        action="safety matter escalated",
        patient_case_id=record.patient_ref,
        referral_episode_id=record.episode_ref,
        actor_id=auth.actor_id or auth.subject,
        actor_name=auth.actor_name,
        actor_role=auth.role,
        actor_auth_source=auth.auth_source,
        new_state=escalation_dict(row),
        reason=row.reason,
        supervisor_required=True,
        supervisor_approval_status="pending",
        compliance_domain="clinical_governance" if record.domain in {"patient", "mixed"} else "workforce_governance",
        risk_level=record.severity,
        source_module="safety-control-v25",
        source_record_ref=row.escalation_ref,
        causation_event_ref=record.evidence_event_ref,
        entity_type="safety_escalation",
        entity_id=row.escalation_ref,
        idempotency_key=f"safety-escalation:create:{row.escalation_ref}",
    )
    row.evidence_event_ref = event.event_ref
    session.add(row)
    record.status = "escalated"
    record.escalated_at = utc_now()
    record.version += 1
    record.updated_at = utc_now()
    session.add(record)
    _new_work_item(
        session,
        record,
        title=f"Escalated safety matter: {record.title}",
        description=row.reason,
        urgency=record.severity,
        owner_role=to_role,
        due_at=row.due_at,
    )
    return row


def evaluate_overdue(session: Session, auth: AuthContext) -> list[SafetyEscalationV25]:
    now = utc_now()
    created: list[SafetyEscalationV25] = []
    records = session.exec(select(SafetyRecordV25).where(SafetyRecordV25.status.in_(OPEN_RECORD_STATUSES))).all()
    for record in records:
        overdue = bool(record.due_at and record.due_at < now)
        actions = session.exec(select(SafetyActionV25).where(SafetyActionV25.record_ref == record.record_ref, SafetyActionV25.status != "completed")).all()
        overdue_actions = [action for action in actions if action.due_at and action.due_at < now]
        if not overdue and not overdue_actions:
            continue
        existing = session.exec(select(SafetyEscalationV25).where(SafetyEscalationV25.record_ref == record.record_ref, SafetyEscalationV25.status == "open")).first()
        if existing:
            continue
        reason = "Safety record overdue" if overdue else f"{len(overdue_actions)} safety action(s) overdue"
        created.append(create_escalation(session, record, auth, {"reason": reason, "to": {"role": "governance_lead"}}))
    return created


def closure_gate(session: Session, record: SafetyRecordV25) -> dict[str, Any]:
    actions = session.exec(select(SafetyActionV25).where(SafetyActionV25.record_ref == record.record_ref)).all()
    blockers: list[dict[str, str]] = []
    if not actions:
        blockers.append({"code": "no_safety_actions", "message": "At least one recorded action is required"})
    for action in actions:
        if action.status != "completed":
            blockers.append({"code": "open_action", "message": f"Action {action.action_ref} is not completed"})
        if action.requires_independent_verification and action.verification_status != "verified":
            blockers.append({"code": "unverified_action", "message": f"Action {action.action_ref} lacks independent verification"})
    if record.severity in {"red", "critical"}:
        if not record.root_cause or len(record.root_cause.strip()) < 12:
            blockers.append({"code": "root_cause_missing", "message": "Red and critical records require a meaningful root-cause statement"})
        if not record.recurrence_controls:
            blockers.append({"code": "recurrence_controls_missing", "message": "Red and critical records require recurrence controls"})
        review = session.exec(
            select(SafetyDecisionV25).where(
                SafetyDecisionV25.record_ref == record.record_ref,
                SafetyDecisionV25.decision_type == "closure_review",
                SafetyDecisionV25.decision == "approved",
            ).order_by(SafetyDecisionV25.created_at.desc())
        ).first()
        if not review:
            blockers.append({"code": "independent_closure_review_missing", "message": "Independent closure approval is required"})
    return {"eligible": not blockers, "blockers": blockers, "actionCount": len(actions)}


def review_closure(session: Session, record: SafetyRecordV25, auth: AuthContext, data: dict[str, Any]) -> SafetyDecisionV25:
    if auth.role not in SENIOR_ROLES and auth.subject != record.independent_owner_subject:
        raise HTTPException(status_code=403, detail="independent owner or senior role required")
    if auth.subject in {record.created_by_subject, record.accountable_owner_subject, record.clinical_owner_subject}:
        raise HTTPException(status_code=409, detail={"code": "independent_closure_reviewer_required"})
    decision = str(data.get("decision") or "").strip().lower()
    if decision not in {"approved", "rejected"}:
        raise HTTPException(status_code=400, detail="decision must be approved or rejected")
    reason = str(data.get("reason") or "").strip()
    if len(reason) < 8:
        raise HTTPException(status_code=400, detail="closure review reason is required")
    gate = closure_gate(session, record)
    if decision == "approved" and any(item["code"] not in {"independent_closure_review_missing"} for item in gate["blockers"]):
        raise HTTPException(status_code=409, detail={"code": "closure_gate_blocked", "blockers": gate["blockers"]})
    return create_decision(
        session,
        record,
        auth,
        decision_type="closure_review",
        decision=decision,
        reason=reason,
        previous_state=sensitive_record_dict(record),
        result_state={"closureGate": gate},
    )


def close_record(session: Session, record: SafetyRecordV25, auth: AuthContext, data: dict[str, Any]) -> SafetyDecisionV25:
    if auth.role not in SENIOR_ROLES:
        raise HTTPException(status_code=403, detail="senior role required to close safety records")
    require_expected_version(record.version, int(data.get("expectedVersion")))
    if is_conflicted(record, auth):
        raise HTTPException(status_code=403, detail={"code": "conflicted_actor_cannot_close"})
    root_cause = str(data.get("rootCause") or record.root_cause or "").strip()
    recurrence = [str(item).strip() for item in (data.get("recurrenceControls") or record.recurrence_controls or []) if str(item).strip()]
    record.root_cause = root_cause or None
    record.recurrence_controls = recurrence
    session.add(record)
    gate = closure_gate(session, record)
    if not gate["eligible"]:
        raise HTTPException(status_code=409, detail={"code": "closure_gate_blocked", "blockers": gate["blockers"]})
    before = sensitive_record_dict(record)
    record.status = "closed"
    record.closed_at = utc_now()
    record.version += 1
    record.updated_at = utc_now()
    session.add(record)
    after = sensitive_record_dict(record)
    return create_decision(
        session,
        record,
        auth,
        decision_type="closure",
        decision="closed",
        reason=str(data.get("reason") or "verified safety actions completed and independently reviewed"),
        previous_state=before,
        result_state=after,
    )


def reopen_record(session: Session, record: SafetyRecordV25, auth: AuthContext, data: dict[str, Any]) -> SafetyDecisionV25:
    if auth.role not in SENIOR_ROLES:
        raise HTTPException(status_code=403, detail="senior role required to reopen safety records")
    require_expected_version(record.version, int(data.get("expectedVersion")))
    reason = str(data.get("reason") or "").strip()
    if len(reason) < 8:
        raise HTTPException(status_code=400, detail="reopen reason is required")
    before = sensitive_record_dict(record)
    record.status = "investigation"
    record.closed_at = None
    record.version += 1
    record.updated_at = utc_now()
    session.add(record)
    after = sensitive_record_dict(record)
    return create_decision(
        session,
        record,
        auth,
        decision_type="reopen",
        decision="reopened",
        reason=reason,
        previous_state=before,
        result_state=after,
    )
