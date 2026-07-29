from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import uuid4

from fastapi import HTTPException
from sqlmodel import Session, select

from app.auth import AuthContext
from app.evidence_service import create_evidence_event
from app.operating_context_v26_service import OperatingContext, assert_payload_context
from app.operational_context_v26_models import (
    CanonicalCommandV26,
    LegacyRouteConvergenceV26,
    OperationalImpactV26,
)
from app.safety_control_v25_models import SafetyRecordV25
from app.safety_control_v25_service import create_action, create_record, sensitive_record_dict

COMMAND_TYPES = {
    "patient_blocker",
    "handover_request",
    "critical_result_received",
    "consent_review_request",
    "estimate_review_request",
    "discharge_review_request",
    "safety_escalation",
    "service_restriction",
    "equipment_downtime",
    "medication_supply_delay",
}
CLINICAL_COMMANDS = {
    "patient_blocker",
    "handover_request",
    "critical_result_received",
    "consent_review_request",
    "discharge_review_request",
}
SENIOR_COMMANDS = {"service_restriction", "equipment_downtime", "safety_escalation"}


def new_ref(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def json_safe(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(item) for item in value]
    return value


def command_dict(row: CanonicalCommandV26) -> dict[str, Any]:
    return {
        "commandRef": row.command_ref,
        "commandType": row.command_type,
        "organisationRef": row.organisation_ref,
        "siteRef": row.site_ref,
        "premisesRef": row.premises_ref,
        "patientRef": row.patient_ref,
        "episodeRef": row.episode_ref,
        "sourceRoute": row.source_route,
        "sourceModule": row.source_module,
        "sourceRecordRef": row.source_record_ref,
        "legacyRouteKey": row.legacy_route_key,
        "requestPayload": row.request_payload,
        "outcomePayload": row.outcome_payload,
        "status": row.status,
        "requiresHumanDecision": row.requires_human_decision,
        "clinicalMutationPerformed": row.clinical_mutation_performed,
        "safetyRecordRef": row.safety_record_ref,
        "evidenceEventRef": row.evidence_event_ref,
        "idempotencyKey": row.idempotency_key,
        "actor": {"subject": row.actor_subject, "name": row.actor_name, "role": row.actor_role},
        "createdAt": row.created_at.isoformat(),
    }


def impact_dict(row: OperationalImpactV26) -> dict[str, Any]:
    return {
        "impactRef": row.impact_ref,
        "commandRef": row.command_ref,
        "organisationRef": row.organisation_ref,
        "siteRef": row.site_ref,
        "premisesRef": row.premises_ref,
        "impactType": row.impact_type,
        "severity": row.severity,
        "serviceRef": row.service_ref,
        "patientRefs": row.patient_refs or [],
        "affectedPatientCount": row.affected_patient_count,
        "boardSummary": row.board_summary,
        "restrictedDetailRef": row.restricted_detail_ref,
        "status": row.status,
        "ownerSubject": row.owner_subject,
        "ownerRole": row.owner_role,
        "dueAt": row.due_at.isoformat() if row.due_at else None,
        "createdAt": row.created_at.isoformat(),
        "resolvedAt": row.resolved_at.isoformat() if row.resolved_at else None,
    }


def _safety_data(
    command_type: str,
    context: OperatingContext,
    auth: AuthContext,
    payload: dict[str, Any],
    command_ref: str,
) -> dict[str, Any]:
    patient_ref = payload.get("patientRef") or payload.get("patientCaseId")
    episode_ref = payload.get("episodeRef") or payload.get("referralEpisodeId")
    summary = str(payload.get("summary") or payload.get("note") or payload.get("reason") or command_type.replace("_", " "))
    severity = str(payload.get("severity") or ("red" if command_type in {"critical_result_received", "patient_blocker", "equipment_downtime"} else "amber")).lower()
    title = {
        "patient_blocker": "Patient workflow blocker",
        "handover_request": "Accountable handover awaiting acceptance",
        "critical_result_received": "Critical result awaiting human acknowledgement",
        "consent_review_request": "Consent review required before progression",
        "estimate_review_request": "Estimate review required",
        "discharge_review_request": "Discharge review required",
        "safety_escalation": "Safety escalation requires named response",
        "service_restriction": "Hospital service restriction",
        "equipment_downtime": "Equipment downtime affecting patient flow",
        "medication_supply_delay": "Medication supply delay",
    }[command_type]
    domain = "patient" if patient_ref or episode_ref else "operations"
    patient_refs = [str(item) for item in (payload.get("patientRefs") or []) if item]
    if patient_ref and str(patient_ref) not in patient_refs:
        patient_refs.append(str(patient_ref))
    return {
        "recordType": "patient_safety" if domain == "patient" else "operational_failure",
        "domain": domain,
        "confidentiality": "standard",
        "severity": severity,
        "title": title,
        "summary": summary,
        "description": str(payload.get("description") or ""),
        "premisesRef": context.premises_ref,
        "patientRef": patient_ref,
        "episodeRef": episode_ref,
        "sourceModule": "operational-convergence-v26",
        "sourceRecordRef": command_ref,
        "immediateRisk": severity in {"red", "critical"},
        "safetyHoldRequested": command_type in {
            "patient_blocker",
            "consent_review_request",
            "discharge_review_request",
        },
        "operationalImpact": {
            "commandType": command_type,
            "siteRef": context.site_ref,
            "premisesRef": context.premises_ref,
            "serviceRef": payload.get("serviceRef"),
            "affectedPatientCount": len(patient_refs),
            "sourceRoute": payload.get("_sourceRoute"),
        },
        "protectiveSummary": str(payload.get("boardSummary") or f"{title} — named human review remains required."),
        # The person creating the record retains accountable responsibility until
        # the target human explicitly accepts or completes the assigned action.
        "owners": {
            "clinical" if domain == "patient" else "accountable": {
                "subject": auth.subject,
                "name": auth.actor_name,
                "role": auth.role,
            }
        },
        "links": [{
            "entityType": "canonical_command",
            "entityRef": command_ref,
            "relationship": "created_by_command",
            "visibility": "standard",
        }],
    }


def _action_owner(payload: dict[str, Any], auth: AuthContext) -> dict[str, str]:
    subject = str(
        payload.get("assignedSubject")
        or payload.get("assignedTo")
        or payload.get("toSubject")
        or payload.get("toActor")
        or auth.subject
    )
    name = str(
        payload.get("assignedName")
        or payload.get("assignedToName")
        or payload.get("toActor")
        or payload.get("assignedTo")
        or auth.actor_name
    )
    role = str(payload.get("assignedRole") or payload.get("toRole") or auth.role)
    return {"subject": subject, "name": name, "role": role}


def record_command(
    session: Session,
    auth: AuthContext,
    context: OperatingContext,
    *,
    command_type: str,
    payload: dict[str, Any],
    source_route: str,
    source_module: str,
    source_record_ref: str | None = None,
    legacy_route_key: str | None = None,
    idempotency_key: str | None = None,
    outcome_payload: dict[str, Any] | None = None,
    existing_safety_ref: str | None = None,
) -> tuple[CanonicalCommandV26, dict[str, Any] | None, bool]:
    command_type = command_type.strip().lower()
    if command_type not in COMMAND_TYPES:
        raise HTTPException(status_code=400, detail={"code": "unsupported_command_type", "commandType": command_type})
    assert_payload_context(context, payload)
    key = idempotency_key or str(payload.get("idempotencyKey") or "")
    if not key:
        key = f"v26:{command_type}:{source_record_ref or new_ref('request')}"
    existing = session.exec(select(CanonicalCommandV26).where(CanonicalCommandV26.idempotency_key == key)).first()
    if existing:
        safety = None
        if existing.safety_record_ref:
            linked = session.exec(select(SafetyRecordV25).where(SafetyRecordV25.record_ref == existing.safety_record_ref)).first()
            safety = sensitive_record_dict(linked) if linked else None
        return existing, safety, False

    command_ref = str(payload.get("commandRef") or new_ref("command"))
    safe_payload = {
        name: value
        for name, value in payload.items()
        if name not in {"actor", "actorName", "actorRole", "actorSubject", "authSource"}
    }
    safe_payload["_sourceRoute"] = source_route
    safety_data = _safety_data(command_type, context, auth, safe_payload, command_ref)
    if existing_safety_ref:
        safety_record = session.exec(select(SafetyRecordV25).where(SafetyRecordV25.record_ref == existing_safety_ref)).first()
        if not safety_record:
            raise HTTPException(status_code=409, detail={"code": "linked_safety_record_missing", "recordRef": existing_safety_ref})
        if safety_record.premises_ref in {"", "default-premises"}:
            safety_record.premises_ref = context.premises_ref
            session.add(safety_record)
    else:
        safety_record, _ = create_record(session, auth, safety_data)

    action_owner = _action_owner(safe_payload, auth)
    record_owner = (
        safety_data.get("owners", {}).get("clinical")
        or safety_data.get("owners", {}).get("accountable")
        or {"subject": auth.subject, "name": auth.actor_name, "role": auth.role}
    )
    action_title = {
        "handover_request": "Named recipient must accept or reject handover",
        "critical_result_received": "Named clinician must acknowledge and record action",
        "consent_review_request": "Authorised clinician must verify consent evidence",
        "estimate_review_request": "Named owner must verify estimate discussion",
        "discharge_review_request": "Authorised clinician must decide discharge readiness",
        "patient_blocker": "Named clinician must review and clear patient blocker",
        "service_restriction": "Named operational owner must review service capacity",
        "equipment_downtime": "Named operational owner must restore or restrict service",
        "medication_supply_delay": "Named clinical and pharmacy owner must agree safe plan",
        "safety_escalation": "Named senior owner must accept safety escalation",
    }[command_type]
    create_action(session, safety_record, auth, {
        "actionType": "clinical_review" if command_type in CLINICAL_COMMANDS else "operational",
        "title": action_title,
        "description": str(safe_payload.get("summary") or safe_payload.get("reason") or action_title),
        "owner": action_owner,
        "dueAt": safe_payload.get("dueAt"),
        "requiresIndependentVerification": command_type in {
            "critical_result_received",
            "patient_blocker",
            "equipment_downtime",
            "medication_supply_delay",
        },
    })

    patient_ref = safe_payload.get("patientRef") or safe_payload.get("patientCaseId")
    episode_ref = safe_payload.get("episodeRef") or safe_payload.get("referralEpisodeId")
    row = CanonicalCommandV26(
        command_ref=command_ref,
        command_type=command_type,
        organisation_ref=context.organisation_ref,
        site_ref=context.site_ref,
        premises_ref=context.premises_ref,
        patient_ref=str(patient_ref) if patient_ref else None,
        episode_ref=str(episode_ref) if episode_ref else None,
        source_route=source_route,
        source_module=source_module,
        source_record_ref=source_record_ref,
        legacy_route_key=legacy_route_key,
        request_payload=json_safe(safe_payload),
        outcome_payload=json_safe(outcome_payload or {}),
        status="human_review_required",
        requires_human_decision=True,
        clinical_mutation_performed=False,
        safety_record_ref=safety_record.record_ref,
        idempotency_key=key,
        actor_subject=auth.subject,
        actor_name=auth.actor_name,
        actor_role=auth.role,
        actor_auth_source=auth.auth_source,
    )
    session.add(row)
    session.flush()

    patient_refs = [str(item) for item in (safe_payload.get("patientRefs") or []) if item]
    if patient_ref and str(patient_ref) not in patient_refs:
        patient_refs.append(str(patient_ref))
    impact = OperationalImpactV26(
        impact_ref=new_ref("impact"),
        command_ref=row.command_ref,
        organisation_ref=context.organisation_ref,
        site_ref=context.site_ref,
        premises_ref=context.premises_ref,
        impact_type=command_type,
        severity=safety_record.severity,
        service_ref=safe_payload.get("serviceRef"),
        patient_refs=patient_refs,
        affected_patient_count=len(patient_refs),
        board_summary=str(safety_data.get("protectiveSummary") or safety_data["title"]),
        restricted_detail_ref=safety_record.record_ref if safety_record.confidentiality != "standard" else None,
        owner_subject=str(record_owner.get("subject") or auth.subject),
        owner_role=str(record_owner.get("role") or auth.role),
        due_at=safe_payload.get("dueAt"),
    )
    session.add(impact)
    event, _ = create_evidence_event(
        session,
        event_type="canonical_operational_command",
        action=f"canonical command recorded: {command_type}",
        patient_case_id=row.patient_ref,
        referral_episode_id=row.episode_ref,
        actor_id=auth.actor_id or auth.subject,
        actor_name=auth.actor_name,
        actor_role=auth.role,
        actor_auth_source=auth.auth_source,
        new_state=command_dict(row),
        reason=str(safe_payload.get("summary") or safe_payload.get("reason") or command_type),
        supervisor_required=safety_record.severity in {"red", "critical"},
        supervisor_approval_status="pending" if safety_record.severity in {"red", "critical"} else "not_required",
        compliance_domain="clinical_governance" if command_type in CLINICAL_COMMANDS else "operational_governance",
        risk_level=safety_record.severity,
        source_module="operational-convergence-v26",
        source_record_ref=row.command_ref,
        entity_type="canonical_command",
        entity_id=row.command_ref,
        idempotency_key=f"evidence:{key}",
    )
    row.evidence_event_ref = event.event_ref
    session.add(row)
    return row, sensitive_record_dict(safety_record), True


def update_linked_command(
    session: Session,
    auth: AuthContext,
    context: OperatingContext,
    *,
    command_type: str,
    source_record_ref: str,
    status: str,
    outcome_payload: dict[str, Any],
    reason: str,
) -> CanonicalCommandV26:
    row = session.exec(select(CanonicalCommandV26).where(
        CanonicalCommandV26.command_type == command_type,
        CanonicalCommandV26.source_record_ref == source_record_ref,
    )).first()
    if not row:
        raise HTTPException(status_code=409, detail={
            "code": "canonical_command_not_found",
            "commandType": command_type,
            "sourceRecordRef": source_record_ref,
        })
    if (row.organisation_ref, row.site_ref, row.premises_ref) != (
        context.organisation_ref,
        context.site_ref,
        context.premises_ref,
    ):
        raise HTTPException(status_code=409, detail={
            "code": "cross_site_command_decision_rejected",
            "activeSiteRef": context.site_ref,
            "commandSiteRef": row.site_ref,
        })
    previous = command_dict(row)
    row.status = status
    row.outcome_payload = json_safe(outcome_payload)
    session.add(row)
    event, _ = create_evidence_event(
        session,
        event_type="canonical_command_outcome",
        action=f"canonical command outcome: {status}",
        patient_case_id=row.patient_ref,
        referral_episode_id=row.episode_ref,
        actor_id=auth.actor_id or auth.subject,
        actor_name=auth.actor_name,
        actor_role=auth.role,
        actor_auth_source=auth.auth_source,
        previous_state=previous,
        new_state=command_dict(row),
        reason=reason,
        compliance_domain="clinical_governance" if command_type in CLINICAL_COMMANDS else "operational_governance",
        risk_level="green" if status in {"accepted", "acknowledged", "completed"} else "red",
        source_module="operational-convergence-v26",
        source_record_ref=row.command_ref,
        causation_event_ref=row.evidence_event_ref,
        entity_type="canonical_command",
        entity_id=row.command_ref,
        idempotency_key=f"command-outcome:{row.command_ref}:{status}",
    )
    row.evidence_event_ref = event.event_ref
    session.add(row)
    return row


def active_impacts(
    session: Session,
    context: OperatingContext,
    *,
    patient_ref: str | None = None,
    episode_ref: str | None = None,
) -> list[OperationalImpactV26]:
    rows = session.exec(select(OperationalImpactV26).where(
        OperationalImpactV26.organisation_ref == context.organisation_ref,
        OperationalImpactV26.site_ref == context.site_ref,
        OperationalImpactV26.premises_ref == context.premises_ref,
        OperationalImpactV26.status == "active",
    ).order_by(OperationalImpactV26.created_at.desc())).all()
    if patient_ref:
        rows = [row for row in rows if patient_ref in (row.patient_refs or [])]
    if episode_ref:
        command_refs = {
            row.command_ref
            for row in session.exec(select(CanonicalCommandV26).where(
                CanonicalCommandV26.episode_ref == episode_ref,
                CanonicalCommandV26.site_ref == context.site_ref,
            )).all()
        }
        rows = [row for row in rows if row.command_ref in command_refs]
    return rows


def seed_legacy_routes(session: Session) -> None:
    routes = [
        ("patient-care-state", "PATCH", "/api/patient-care/episodes/{episode_id}/state", "patient_blocker"),
        ("control-plane-handover-create", "POST", "/api/control-plane/handovers", "handover_request"),
        ("control-plane-critical-result-create", "POST", "/api/control-plane/critical-results", "critical_result_received"),
        ("consent-review", "POST", "/api/v26/commands", "consent_review_request"),
        ("estimate-review", "POST", "/api/v26/commands", "estimate_review_request"),
        ("discharge-review", "POST", "/api/v26/commands", "discharge_review_request"),
    ]
    for key, method, path, command_type in routes:
        if session.exec(select(LegacyRouteConvergenceV26).where(LegacyRouteConvergenceV26.route_key == key)).first():
            continue
        session.add(LegacyRouteConvergenceV26(
            route_key=key,
            method=method,
            legacy_path=path,
            canonical_command_type=command_type,
            canonical_path="/api/v26/commands",
            reason="One authenticated command and evidence path per hospital action.",
        ))
    session.flush()
