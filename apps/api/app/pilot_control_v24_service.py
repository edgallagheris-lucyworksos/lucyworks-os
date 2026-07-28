from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import HTTPException
from sqlmodel import Session, select

from app.auth import AuthContext, CLINICAL_ROLES
from app.automation_operator_control_v23_routes import validate_service_configuration
from app.evidence_service import create_evidence_event
from app.event_driven_automation_v22_service import runtime_settings
from app.hospital_ops_models import CanonicalEpisodeState
from app.pilot_control_v24_models import (
    PilotApprovalV24,
    PilotAuthorityV24,
    PilotControlActionV24,
    PilotShadowComparisonV24,
    PilotUATScenarioV24,
)
from app.production_readiness_models import PilotObservation, PilotRun, ReadinessControl
from app.production_readiness_service import (
    SHADOW_REQUIRED,
    control_dict,
    gate_summary,
    pilot_dict,
    seed_controls,
    update_control,
)


SUPPORTED_PILOT_MODES = {"synthetic", "shadow", "bounded_live"}
PILOT_ACKNOWLEDGEMENTS = {
    "synthetic": "AUTHORISE SYNTHETIC VALIDATION",
    "shadow": "AUTHORISE SHADOW MODE ONLY",
    "bounded_live": "AUTHORISE BOUNDED LIVE PILOT WITH HUMAN CLINICAL AUTHORITY",
}
APPROVAL_ACKNOWLEDGEMENT = "APPROVE PILOT CONTROL BOUNDARY"
ROLLBACK_ACKNOWLEDGEMENT = "INITIATE PILOT ROLLBACK"
PILOT_CLINICAL_OWNER_ROLES = {"clinician", "clinical_director", "senior_clinician", "supervisor"}
APPROVAL_ROLES = {
    "clinical": {"clinical_director", "senior_clinician", "supervisor"},
    "operational": {"hospital_director", "ops_manager", "supervisor"},
    "governance": {"governance_lead", "hospital_director", "clinical_director"},
}
TERMINAL_AUTHORITY_STATES = {"rollback", "completed"}

UAT_SCENARIOS: tuple[dict[str, Any], ...] = (
    {
        "code": "referral_identity",
        "title": "Referral identity and duplicate prevention",
        "role": "reception",
        "workflow": "Receive a referral, resolve patient and owner identity, and prevent an unsafe duplicate record.",
        "expected": "The user can see the evidence used, resolve ambiguity, and reach one canonical episode without silent merging.",
        "critical": True,
    },
    {
        "code": "triage_acceptance",
        "title": "Triage, acceptance and accountable ownership",
        "role": "clinician",
        "workflow": "Triage a referral, accept or decline it, and assign the next accountable owner and deadline.",
        "expected": "The decision, reason, owner, urgency and evidence are visible and no clinical decision is delegated to automation.",
        "critical": True,
    },
    {
        "code": "consent_estimate",
        "title": "Consent, estimate and financial authority",
        "role": "clinician",
        "workflow": "Record consent scope, estimate authority and any limitation before treatment proceeds.",
        "expected": "Missing or expired authority blocks the relevant transition and creates owned work rather than fabricated completion.",
        "critical": True,
    },
    {
        "code": "schedule_resource",
        "title": "Theatre, imaging and resource coordination",
        "role": "ops_manager",
        "workflow": "Schedule a procedure with room, staff, assistant, equipment, preparation, recovery and turnover requirements.",
        "expected": "Conflicts and displacement are visible on the single master board before a versioned human command is applied.",
        "critical": True,
    },
    {
        "code": "observation_escalation",
        "title": "Clinical observation escalation",
        "role": "nurse",
        "workflow": "Record green, amber and red observations and follow the escalation workflow.",
        "expected": "Recorded facts remain unchanged; automation may create human-owned review work but cannot interpret or treat the patient.",
        "critical": True,
    },
    {
        "code": "critical_result",
        "title": "Critical result acknowledgement",
        "role": "clinician",
        "workflow": "Receive a critical result, route it to a responsible professional and record acknowledgement.",
        "expected": "Overdue results remain visible and automation never records acknowledgement on behalf of a professional.",
        "critical": True,
    },
    {
        "code": "medication_governance",
        "title": "Medication proposal, prescription and administration",
        "role": "clinician",
        "workflow": "Calculate a proposal, authorise an order and record administration with controlled-drug safeguards where relevant.",
        "expected": "Proposal, prescription and administration remain distinct, attributed actions with dose and identity checks.",
        "critical": True,
    },
    {
        "code": "handover_discharge",
        "title": "Handover and discharge evidence",
        "role": "clinician",
        "workflow": "Handover a patient between teams and complete discharge readiness and owner communication.",
        "expected": "The receiving owner, outstanding work and evidence gaps are explicit; discharge is never inferred or automated.",
        "critical": True,
    },
    {
        "code": "emergency_override",
        "title": "Emergency insertion and displacement control",
        "role": "supervisor",
        "workflow": "Insert an emergency case, inspect displacement options and apply a named override.",
        "expected": "Affected patients, staff, areas, deadlines and alternatives are shown before the accountable command is committed.",
        "critical": True,
    },
    {
        "code": "downtime_rollback",
        "title": "Downtime, stop and rollback",
        "role": "ops_manager",
        "workflow": "Exercise loss of an integration or service, stop the pilot and execute the documented rollback plan.",
        "expected": "Stop remains immediately available, rollback ownership is clear and recovery evidence is retained.",
        "critical": True,
    },
    {
        "code": "privacy_access",
        "title": "Privacy, access and audit review",
        "role": "governance_lead",
        "workflow": "Review role access, evidence attribution, export, correction and retention controls.",
        "expected": "Access follows the configured role model and material actions can be reconstructed from immutable evidence.",
        "critical": True,
    },
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_ref(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def _clean(value: Any, maximum: int = 2000) -> str:
    return " ".join(str(value or "").split())[:maximum]


def authority_payload(row: PilotAuthorityV24) -> dict[str, Any]:
    return {
        "authorityRef": row.authority_ref,
        "runRef": row.run_ref,
        "premisesRef": row.premises_ref,
        "serviceLine": row.service_line,
        "requestedMode": row.requested_mode,
        "status": row.status,
        "scope": row.scope,
        "successCriteria": row.success_criteria,
        "stopCriteria": row.stop_criteria,
        "rollbackPlan": row.rollback_plan,
        "integrationScope": row.integration_scope,
        "automationMode": row.automation_mode,
        "accountableOwner": {
            "subject": row.accountable_owner_subject,
            "name": row.accountable_owner_name,
            "role": row.accountable_owner_role,
        },
        "clinicalOwner": {
            "subject": row.clinical_owner_subject,
            "name": row.clinical_owner_name,
            "role": row.clinical_owner_role,
        } if row.clinical_owner_subject else None,
        "activatedAt": row.activated_at.isoformat() if row.activated_at else None,
        "stoppedAt": row.stopped_at.isoformat() if row.stopped_at else None,
        "rollbackAt": row.rollback_at.isoformat() if row.rollback_at else None,
        "completedAt": row.completed_at.isoformat() if row.completed_at else None,
        "planVersion": row.plan_version,
        "version": row.version,
        "evidenceEventRef": row.evidence_event_ref,
        "createdBy": {"subject": row.created_by_subject, "name": row.created_by_name},
        "createdAt": row.created_at.isoformat(),
        "updatedAt": row.updated_at.isoformat(),
    }


def approval_payload(row: PilotApprovalV24) -> dict[str, Any]:
    return {
        "approvalRef": row.approval_ref,
        "authorityRef": row.authority_ref,
        "approvalType": row.approval_type,
        "decision": row.decision,
        "reason": row.reason,
        "acknowledgement": row.acknowledgement,
        "planVersion": row.authority_version,
        "actor": {
            "subject": row.actor_subject,
            "name": row.actor_name,
            "role": row.actor_role,
            "authSource": row.actor_auth_source,
        },
        "evidenceEventRef": row.evidence_event_ref,
        "createdAt": row.created_at.isoformat(),
    }


def action_payload(row: PilotControlActionV24) -> dict[str, Any]:
    return {
        "actionRef": row.action_ref,
        "authorityRef": row.authority_ref,
        "actionType": row.action_type,
        "reason": row.reason,
        "previousStatus": row.previous_status,
        "resultStatus": row.result_status,
        "previousState": row.previous_state,
        "resultState": row.result_state,
        "actor": {
            "subject": row.actor_subject,
            "name": row.actor_name,
            "role": row.actor_role,
            "authSource": row.actor_auth_source,
        },
        "evidenceEventRef": row.evidence_event_ref,
        "createdAt": row.created_at.isoformat(),
    }


def comparison_payload(row: PilotShadowComparisonV24) -> dict[str, Any]:
    return {
        "comparisonRef": row.comparison_ref,
        "authorityRef": row.authority_ref,
        "externalRef": row.external_ref,
        "canonicalEpisodeRef": row.canonical_episode_ref,
        "patientRef": row.patient_ref,
        "sourceSystem": row.source_system,
        "externalSnapshot": row.external_snapshot,
        "canonicalSnapshot": row.canonical_snapshot,
        "mismatchCodes": row.mismatch_codes,
        "severity": row.severity,
        "status": row.status,
        "reviewedBy": {
            "subject": row.reviewed_by_subject,
            "name": row.reviewed_by_name,
        } if row.reviewed_by_subject else None,
        "reviewNote": row.review_note,
        "reviewedAt": row.reviewed_at.isoformat() if row.reviewed_at else None,
        "version": row.version,
        "createdAt": row.created_at.isoformat(),
        "updatedAt": row.updated_at.isoformat(),
    }


def scenario_payload(row: PilotUATScenarioV24) -> dict[str, Any]:
    return {
        "scenarioRef": row.scenario_ref,
        "authorityRef": row.authority_ref,
        "scenarioCode": row.scenario_code,
        "title": row.title,
        "actorRole": row.actor_role,
        "workflow": row.workflow,
        "expectedOutcome": row.expected_outcome,
        "critical": row.critical,
        "status": row.status,
        "evidenceSummary": row.evidence_summary,
        "testedBy": {
            "subject": row.tested_by_subject,
            "name": row.tested_by_name,
        } if row.tested_by_subject else None,
        "testedAt": row.tested_at.isoformat() if row.tested_at else None,
        "version": row.version,
        "createdAt": row.created_at.isoformat(),
        "updatedAt": row.updated_at.isoformat(),
    }


def require_authority(session: Session, authority_ref: str, *, lock: bool = False) -> PilotAuthorityV24:
    query = select(PilotAuthorityV24).where(PilotAuthorityV24.authority_ref == authority_ref)
    if lock:
        query = query.with_for_update()
    row = session.exec(query).first()
    if not row:
        raise HTTPException(status_code=404, detail="pilot authority not found")
    return row


def require_version(row: PilotAuthorityV24, expected_version: int) -> None:
    if row.version != expected_version:
        raise HTTPException(
            status_code=409,
            detail={"code": "stale_pilot_authority", "currentVersion": row.version, "planVersion": row.plan_version},
        )


def _pilot_run(session: Session, row: PilotAuthorityV24) -> PilotRun:
    run = session.exec(select(PilotRun).where(PilotRun.run_ref == row.run_ref)).first()
    if not run:
        raise HTTPException(status_code=409, detail="linked production-readiness pilot run is missing")
    return run


def seed_uat_scenarios(session: Session, authority_ref: str) -> list[PilotUATScenarioV24]:
    existing = {
        row.scenario_code: row
        for row in session.exec(
            select(PilotUATScenarioV24).where(PilotUATScenarioV24.authority_ref == authority_ref)
        ).all()
    }
    output: list[PilotUATScenarioV24] = []
    for definition in UAT_SCENARIOS:
        row = existing.get(str(definition["code"]))
        if not row:
            row = PilotUATScenarioV24(
                scenario_ref=new_ref("pilot-uat-v24"),
                authority_ref=authority_ref,
                scenario_code=str(definition["code"]),
                title=str(definition["title"]),
                actor_role=str(definition["role"]),
                workflow=str(definition["workflow"]),
                expected_outcome=str(definition["expected"]),
                critical=bool(definition["critical"]),
            )
            session.add(row)
        output.append(row)
    session.flush()
    return output


def record_action(
    session: Session,
    row: PilotAuthorityV24,
    *,
    action_type: str,
    reason: str,
    auth: AuthContext,
    previous_state: dict[str, Any],
    result_state: dict[str, Any],
    risk_level: str = "amber",
) -> PilotControlActionV24:
    action = PilotControlActionV24(
        action_ref=new_ref("pilot-action-v24"),
        authority_ref=row.authority_ref,
        action_type=action_type,
        reason=_clean(reason),
        previous_status=previous_state.get("status"),
        result_status=result_state.get("status"),
        previous_state=previous_state,
        result_state=result_state,
        actor_subject=auth.subject,
        actor_name=auth.actor_name,
        actor_role=auth.role,
        actor_auth_source=auth.auth_source,
    )
    session.add(action)
    session.flush()
    evidence, _ = create_evidence_event(
        session,
        event_type=f"pilot_control_{action_type}",
        action=action_type,
        actor_id=auth.actor_id,
        actor_name=auth.actor_name,
        actor_role=auth.role,
        actor_auth_source=auth.auth_source,
        previous_state=previous_state,
        new_state=result_state,
        reason=reason,
        justification="Bounded hospital pilot authority and recovery control",
        evidence_links=[{"type": "pilot_authority", "id": row.authority_ref}, {"type": "pilot_run", "id": row.run_ref}],
        compliance_domain="clinical_governance",
        risk_level=risk_level,
        source_module="pilot-control-v24",
        source_record_ref=action.action_ref,
        correlation_id=row.authority_ref,
        entity_type="pilot_authority",
        entity_id=row.authority_ref,
        idempotency_key=f"pilot-control-v24:{action.action_ref}",
    )
    action.evidence_event_ref = evidence.event_ref
    row.evidence_event_ref = evidence.event_ref
    session.add(action)
    session.add(row)
    return action


def create_authority(session: Session, payload: dict[str, Any], auth: AuthContext) -> PilotAuthorityV24:
    mode = str(payload.get("requestedMode") or "synthetic").strip().lower()
    if mode not in SUPPORTED_PILOT_MODES:
        raise HTTPException(status_code=422, detail="unsupported requestedMode")
    service_line = _clean(payload.get("serviceLine") or "referral", 120)
    premises_ref = _clean(payload.get("premisesRef") or "default-premises", 160)
    owner = payload.get("accountableOwner") or {}
    clinical = payload.get("clinicalOwner") or {}
    run = PilotRun(
        run_ref=new_ref("pilot"),
        phase="bounded_pilot" if mode == "bounded_live" else mode,
        service_line=service_line,
        premises_ref=premises_ref,
        status="planned",
        accountable_owner=_clean(owner.get("name") or auth.actor_name, 200),
        success_criteria_json="{}",
        metrics_json="{}",
        blockers_json="[]",
        started_at=None,
        created_by_subject=auth.subject,
    )
    session.add(run)
    session.flush()
    row = PilotAuthorityV24(
        authority_ref=new_ref("pilot-authority-v24"),
        run_ref=run.run_ref,
        premises_ref=premises_ref,
        service_line=service_line,
        requested_mode=mode,
        scope=dict(payload.get("scope") or {}),
        success_criteria=dict(payload.get("successCriteria") or {}),
        stop_criteria=dict(payload.get("stopCriteria") or {}),
        rollback_plan=dict(payload.get("rollbackPlan") or {}),
        integration_scope=list(dict.fromkeys(str(value).strip() for value in payload.get("integrationScope") or [] if str(value).strip())),
        automation_mode=str(payload.get("automationMode") or "disabled").strip().lower(),
        accountable_owner_subject=_clean(owner.get("subject") or auth.subject, 200),
        accountable_owner_name=_clean(owner.get("name") or auth.actor_name, 200),
        accountable_owner_role=_clean(owner.get("role") or auth.role, 80).lower(),
        clinical_owner_subject=_clean(clinical.get("subject"), 200) or None,
        clinical_owner_name=_clean(clinical.get("name"), 200) or None,
        clinical_owner_role=_clean(clinical.get("role"), 80).lower() or None,
        created_by_subject=auth.subject,
        created_by_name=auth.actor_name,
    )
    session.add(row)
    session.flush()
    seed_uat_scenarios(session, row.authority_ref)
    before: dict[str, Any] = {}
    after = authority_payload(row)
    record_action(
        session,
        row,
        action_type="authority_created",
        reason=str(payload.get("reason") or "Create bounded pilot authority plan"),
        auth=auth,
        previous_state=before,
        result_state=after,
    )
    return row


def update_authority(session: Session, authority_ref: str, payload: dict[str, Any], auth: AuthContext) -> PilotAuthorityV24:
    row = require_authority(session, authority_ref, lock=True)
    require_version(row, int(payload.get("expectedVersion")))
    if row.status in {"running", "completed", "rollback"}:
        raise HTTPException(status_code=409, detail="stop an active pilot before changing its authorised plan")
    before = authority_payload(row)
    mode = str(payload.get("requestedMode", row.requested_mode)).strip().lower()
    if mode not in SUPPORTED_PILOT_MODES:
        raise HTTPException(status_code=422, detail="unsupported requestedMode")
    row.requested_mode = mode
    row.service_line = _clean(payload.get("serviceLine", row.service_line), 120)
    if payload.get("scope") is not None:
        row.scope = dict(payload["scope"])
    if payload.get("successCriteria") is not None:
        row.success_criteria = dict(payload["successCriteria"])
    if payload.get("stopCriteria") is not None:
        row.stop_criteria = dict(payload["stopCriteria"])
    if payload.get("rollbackPlan") is not None:
        row.rollback_plan = dict(payload["rollbackPlan"])
    if payload.get("integrationScope") is not None:
        row.integration_scope = list(dict.fromkeys(str(value).strip() for value in payload["integrationScope"] if str(value).strip()))
    if payload.get("automationMode") is not None:
        row.automation_mode = str(payload["automationMode"]).strip().lower()
    owner = payload.get("accountableOwner")
    if owner is not None:
        row.accountable_owner_subject = _clean(owner.get("subject"), 200)
        row.accountable_owner_name = _clean(owner.get("name"), 200)
        row.accountable_owner_role = _clean(owner.get("role"), 80).lower()
    clinical = payload.get("clinicalOwner")
    if clinical is not None:
        row.clinical_owner_subject = _clean(clinical.get("subject"), 200) or None
        row.clinical_owner_name = _clean(clinical.get("name"), 200) or None
        row.clinical_owner_role = _clean(clinical.get("role"), 80).lower() or None
    row.plan_version += 1
    row.version += 1
    row.status = "draft"
    row.updated_at = utc_now()
    run = _pilot_run(session, row)
    run.phase = "bounded_pilot" if mode == "bounded_live" else mode
    run.service_line = row.service_line
    run.accountable_owner = row.accountable_owner_name
    run.status = "planned"
    run.updated_at = utc_now()
    session.add(run)
    session.add(row)
    session.flush()
    record_action(
        session,
        row,
        action_type="plan_changed",
        reason=str(payload.get("reason") or "Pilot authority plan changed"),
        auth=auth,
        previous_state=before,
        result_state=authority_payload(row),
    )
    return row


def _latest_approvals(session: Session, row: PilotAuthorityV24) -> dict[str, PilotApprovalV24]:
    approvals = session.exec(
        select(PilotApprovalV24)
        .where(PilotApprovalV24.authority_ref == row.authority_ref)
        .where(PilotApprovalV24.authority_version == row.plan_version)
        .order_by(PilotApprovalV24.created_at)
    ).all()
    latest: dict[str, PilotApprovalV24] = {}
    for approval in approvals:
        latest[approval.approval_type] = approval
    return latest


def record_approval(session: Session, row: PilotAuthorityV24, payload: dict[str, Any], auth: AuthContext) -> PilotApprovalV24:
    approval_type = str(payload.get("approvalType") or "").strip().lower()
    decision = str(payload.get("decision") or "").strip().lower()
    if approval_type not in APPROVAL_ROLES:
        raise HTTPException(status_code=422, detail="unsupported approvalType")
    if auth.role not in APPROVAL_ROLES[approval_type]:
        raise HTTPException(status_code=403, detail=f"role {auth.role} cannot provide {approval_type} pilot approval")
    if decision not in {"approved", "rejected"}:
        raise HTTPException(status_code=422, detail="decision must be approved or rejected")
    if decision == "approved" and str(payload.get("acknowledgement") or "") != APPROVAL_ACKNOWLEDGEMENT:
        raise HTTPException(status_code=400, detail=f"acknowledgement must be {APPROVAL_ACKNOWLEDGEMENT}")
    reason = _clean(payload.get("reason"))
    if len(reason) < 8:
        raise HTTPException(status_code=422, detail="approval reason must contain at least eight characters")
    approval = PilotApprovalV24(
        approval_ref=new_ref("pilot-approval-v24"),
        authority_ref=row.authority_ref,
        approval_type=approval_type,
        decision=decision,
        reason=reason,
        acknowledgement=str(payload.get("acknowledgement") or "") or None,
        authority_version=row.plan_version,
        actor_subject=auth.subject,
        actor_name=auth.actor_name,
        actor_role=auth.role,
        actor_auth_source=auth.auth_source,
    )
    session.add(approval)
    session.flush()
    evidence, _ = create_evidence_event(
        session,
        event_type="pilot_authority_approval",
        action=f"{approval_type} pilot approval {decision}",
        actor_id=auth.actor_id,
        actor_name=auth.actor_name,
        actor_role=auth.role,
        actor_auth_source=auth.auth_source,
        previous_state=None,
        new_state=approval_payload(approval),
        reason=reason,
        justification="Named multi-role approval for bounded hospital validation",
        evidence_links=[{"type": "pilot_authority", "id": row.authority_ref}],
        compliance_domain="clinical_governance",
        risk_level="green" if decision == "approved" else "red",
        source_module="pilot-control-v24",
        source_record_ref=approval.approval_ref,
        correlation_id=row.authority_ref,
        entity_type="pilot_approval",
        entity_id=approval.approval_ref,
        idempotency_key=f"pilot-approval-v24:{approval.approval_ref}",
    )
    approval.evidence_event_ref = evidence.event_ref
    if decision == "rejected":
        row.status = "blocked"
        row.version += 1
        row.updated_at = utc_now()
        row.evidence_event_ref = evidence.event_ref
        session.add(row)
    session.add(approval)
    return approval


def _scope_valid(scope: dict[str, Any]) -> bool:
    workflows = scope.get("includedWorkflows") or scope.get("workflows") or []
    try:
        max_patients = int(scope.get("maxConcurrentPatients") or scope.get("maxPatients") or 0)
    except (TypeError, ValueError):
        max_patients = 0
    return bool(workflows) and max_patients > 0


def _rollback_valid(plan: dict[str, Any]) -> bool:
    steps = plan.get("steps") or []
    return bool(_clean(plan.get("owner"))) and bool(steps) and bool(_clean(plan.get("recoveryPoint"))) and bool(_clean(plan.get("communications")))


def _stop_valid(criteria: dict[str, Any]) -> bool:
    triggers = criteria.get("triggers") or criteria.get("conditions") or []
    return bool(triggers) and bool(_clean(criteria.get("decisionOwner") or criteria.get("owner")))


def _success_valid(criteria: dict[str, Any]) -> bool:
    return bool(criteria) and bool(criteria.get("measures") or criteria.get("metrics") or criteria.get("acceptance"))


def _blocker(code: str, detail: str, owner_role: str, severity: str = "red") -> dict[str, str]:
    return {"code": code, "detail": detail, "ownerRole": owner_role, "severity": severity}


def gate_for(session: Session, row: PilotAuthorityV24, mode: str | None = None) -> dict[str, Any]:
    target_mode = str(mode or row.requested_mode).strip().lower()
    if target_mode not in SUPPORTED_PILOT_MODES:
        raise HTTPException(status_code=422, detail="unsupported pilot mode")
    controls = seed_controls(session)
    readiness = gate_summary(session)
    controls_by_ref = {control.control_ref: control for control in controls}
    approvals = _latest_approvals(session, row)
    approval_payloads = {key: approval_payload(value) for key, value in approvals.items()}
    observations = session.exec(
        select(PilotObservation).where(PilotObservation.run_ref == row.run_ref, PilotObservation.status != "resolved")
    ).all()
    comparisons = session.exec(
        select(PilotShadowComparisonV24).where(PilotShadowComparisonV24.authority_ref == row.authority_ref)
    ).all()
    scenarios = seed_uat_scenarios(session, row.authority_ref)
    automation = runtime_settings(session, row.premises_ref)
    automation_validation = validate_service_configuration(
        mode=str(automation.get("mode") or "disabled"),
        enabled_trigger_types=list(automation.get("enabledTriggerTypes") or []),
        service_subject=str(automation.get("serviceSubject") or ""),
        service_name=str(automation.get("serviceName") or ""),
        service_role=str(automation.get("serviceRole") or ""),
    )
    blockers: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    if not _scope_valid(row.scope):
        blockers.append(_blocker("scope_incomplete", "Define included workflows and a positive maximum concurrent patient scope.", "ops_manager"))
    if not _success_valid(row.success_criteria):
        blockers.append(_blocker("success_criteria_incomplete", "Define measurable success or acceptance criteria.", "ops_manager"))
    if not _stop_valid(row.stop_criteria):
        blockers.append(_blocker("stop_criteria_incomplete", "Define stop conditions and the named stop-decision owner.", "governance_lead"))
    if not _rollback_valid(row.rollback_plan):
        blockers.append(_blocker("rollback_plan_incomplete", "Define rollback owner, steps, recovery point and communications.", "ops_manager"))
    if not row.accountable_owner_subject or not row.accountable_owner_name or not row.accountable_owner_role:
        blockers.append(_blocker("accountable_owner_missing", "A named accountable operational owner is required.", "hospital_director"))

    if row.automation_mode != str(automation.get("mode") or "disabled"):
        blockers.append(_blocker(
            "automation_mode_mismatch",
            f"Pilot plan expects {row.automation_mode}; site automation is {automation.get('mode') or 'disabled'}.",
            "governance_lead",
        ))
    if target_mode == "shadow" and row.automation_mode not in {"disabled", "preview_only"}:
        blockers.append(_blocker("shadow_automation_boundary", "Shadow mode permits disabled or preview-only automation, not governed work creation.", "governance_lead"))
    if target_mode == "bounded_live" and row.automation_mode == "governed_commit" and not automation_validation["valid"]:
        blockers.append(_blocker("automation_service_invalid", "Governed automation service identity or clinical role validation is incomplete.", "governance_lead"))

    if target_mode in {"shadow", "bounded_live"}:
        required_refs = set(SHADOW_REQUIRED) if target_mode == "shadow" else {
            control.control_ref for control in controls if control.required and control.control_ref != "pilot.bounded"
        }
        missing = sorted(ref for ref in required_refs if controls_by_ref.get(ref) is None or controls_by_ref[ref].status != "passed")
        for control_ref in missing:
            control = controls_by_ref.get(control_ref)
            blockers.append(_blocker(
                f"readiness:{control_ref}",
                control.title if control else f"Missing readiness control {control_ref}",
                control.owner_role if control else "governance_lead",
            ))

    open_red_observations = [item for item in observations if item.severity == "red"]
    if open_red_observations:
        blockers.append(_blocker("open_red_observations", f"{len(open_red_observations)} unresolved red pilot observation(s).", "governance_lead"))
    unresolved_red_comparisons = [
        item for item in comparisons if item.severity == "red" and item.status not in {"approved", "rejected"}
    ]
    if unresolved_red_comparisons:
        blockers.append(_blocker("red_shadow_mismatches", f"{len(unresolved_red_comparisons)} unresolved red shadow comparison(s).", "ops_manager"))
    unresolved_amber_comparisons = [
        item for item in comparisons if item.severity == "amber" and item.status not in {"approved", "rejected", "matched"}
    ]
    if unresolved_amber_comparisons:
        warnings.append(_blocker("amber_shadow_mismatches", f"{len(unresolved_amber_comparisons)} unresolved amber shadow comparison(s).", "ops_manager", "amber"))

    approved = {key: value for key, value in approvals.items() if value.decision == "approved"}
    if target_mode == "shadow" and "operational" not in approved:
        blockers.append(_blocker("operational_approval_missing", "Current plan version requires operational approval.", "ops_manager"))
    if target_mode == "bounded_live":
        if row.clinical_owner_role not in PILOT_CLINICAL_OWNER_ROLES or not row.clinical_owner_subject:
            blockers.append(_blocker("clinical_owner_missing", "A named veterinary clinical owner with decision authority is required.", "clinical_director"))
        for approval_type, owner_role in (("clinical", "clinical_director"), ("operational", "hospital_director"), ("governance", "governance_lead")):
            if approval_type not in approved:
                blockers.append(_blocker(f"{approval_type}_approval_missing", f"Current plan version requires {approval_type} approval.", owner_role))
        if "clinical" in approved and "operational" in approved and approved["clinical"].actor_subject == approved["operational"].actor_subject:
            blockers.append(_blocker("independent_approval_missing", "Clinical and operational approval must be provided by different named people.", "hospital_director"))
        failed_critical = [item for item in scenarios if item.critical and item.status != "passed"]
        if failed_critical:
            blockers.append(_blocker("uat_incomplete", f"{len(failed_critical)} critical UAT scenario(s) are not passed.", "ops_manager"))

    if target_mode == "synthetic":
        blockers = [item for item in blockers if item["code"] in {"scope_incomplete", "success_criteria_incomplete", "stop_criteria_incomplete", "rollback_plan_incomplete", "accountable_owner_missing"}]

    return {
        "authorityRef": row.authority_ref,
        "requestedMode": target_mode,
        "eligible": not blockers,
        "blockers": blockers,
        "warnings": warnings,
        "readiness": readiness,
        "automation": automation,
        "automationValidation": automation_validation,
        "approvals": approval_payloads,
        "approvalAcknowledgement": APPROVAL_ACKNOWLEDGEMENT,
        "authorisationAcknowledgement": PILOT_ACKNOWLEDGEMENTS[target_mode],
        "rollbackAcknowledgement": ROLLBACK_ACKNOWLEDGEMENT,
        "summary": {
            "openObservations": len(observations),
            "openRedObservations": len(open_red_observations),
            "shadowComparisons": len(comparisons),
            "unresolvedRedComparisons": len(unresolved_red_comparisons),
            "uatTotal": len(scenarios),
            "uatPassed": len([item for item in scenarios if item.status == "passed"]),
            "criticalUatRemaining": len([item for item in scenarios if item.critical and item.status != "passed"]),
        },
    }


def authorise(session: Session, row: PilotAuthorityV24, payload: dict[str, Any], auth: AuthContext) -> PilotAuthorityV24:
    require_version(row, int(payload.get("expectedVersion")))
    mode = str(payload.get("mode") or row.requested_mode).strip().lower()
    if mode != row.requested_mode:
        raise HTTPException(status_code=409, detail="authorisation mode must match the approved pilot plan")
    expected_ack = PILOT_ACKNOWLEDGEMENTS[mode]
    if str(payload.get("acknowledgement") or "") != expected_ack:
        raise HTTPException(status_code=400, detail=f"acknowledgement must be {expected_ack}")
    gate = gate_for(session, row, mode)
    if not gate["eligible"]:
        raise HTTPException(status_code=409, detail={"code": "pilot_not_eligible", "blockers": gate["blockers"]})
    before = authority_payload(row)
    row.status = "authorised"
    row.version += 1
    row.updated_at = utc_now()
    run = _pilot_run(session, row)
    run.status = "planned"
    run.approved_by_subject = auth.subject
    run.approval_note = _clean(payload.get("reason"))
    run.updated_at = utc_now()
    session.add(run)
    session.add(row)
    session.flush()
    record_action(
        session,
        row,
        action_type=f"{mode}_authorised",
        reason=str(payload.get("reason") or "Pilot mode authorised"),
        auth=auth,
        previous_state=before,
        result_state=authority_payload(row),
        risk_level="red" if mode == "bounded_live" else "amber",
    )
    return row


def start_authority(session: Session, row: PilotAuthorityV24, payload: dict[str, Any], auth: AuthContext) -> PilotAuthorityV24:
    require_version(row, int(payload.get("expectedVersion")))
    if row.status != "authorised":
        raise HTTPException(status_code=409, detail="pilot must be authorised before it starts")
    before = authority_payload(row)
    row.status = "running"
    row.activated_at = utc_now()
    row.stopped_at = None
    row.version += 1
    row.updated_at = utc_now()
    run = _pilot_run(session, row)
    run.status = "running"
    run.started_at = run.started_at or utc_now()
    run.updated_at = utc_now()
    session.add(run)
    session.add(row)
    session.flush()
    record_action(
        session,
        row,
        action_type="pilot_started",
        reason=str(payload.get("reason") or "Start authorised pilot"),
        auth=auth,
        previous_state=before,
        result_state=authority_payload(row),
        risk_level="red" if row.requested_mode == "bounded_live" else "amber",
    )
    return row


def stop_authority(session: Session, row: PilotAuthorityV24, reason: str, auth: AuthContext) -> tuple[PilotAuthorityV24, PilotControlActionV24 | None]:
    if row.status in {"stopped", "rollback", "completed"}:
        return row, None
    before = authority_payload(row)
    row.status = "stopped"
    row.stopped_at = utc_now()
    row.version += 1
    row.updated_at = utc_now()
    run = _pilot_run(session, row)
    run.status = "blocked"
    run.updated_at = utc_now()
    session.add(run)
    session.add(row)
    session.flush()
    action = record_action(
        session,
        row,
        action_type="pilot_stopped",
        reason=reason,
        auth=auth,
        previous_state=before,
        result_state=authority_payload(row),
        risk_level="red",
    )
    return row, action


def rollback_authority(session: Session, row: PilotAuthorityV24, payload: dict[str, Any], auth: AuthContext) -> PilotAuthorityV24:
    require_version(row, int(payload.get("expectedVersion")))
    if row.status in TERMINAL_AUTHORITY_STATES:
        raise HTTPException(status_code=409, detail="pilot is already terminal")
    if str(payload.get("acknowledgement") or "") != ROLLBACK_ACKNOWLEDGEMENT:
        raise HTTPException(status_code=400, detail=f"acknowledgement must be {ROLLBACK_ACKNOWLEDGEMENT}")
    if not _rollback_valid(row.rollback_plan):
        raise HTTPException(status_code=409, detail="rollback plan is incomplete")
    before = authority_payload(row)
    row.status = "rollback"
    row.rollback_at = utc_now()
    row.version += 1
    row.updated_at = utc_now()
    run = _pilot_run(session, row)
    run.status = "failed"
    run.ended_at = utc_now()
    run.updated_at = utc_now()
    session.add(run)
    session.add(row)
    session.flush()
    record_action(
        session,
        row,
        action_type="pilot_rollback_initiated",
        reason=str(payload.get("reason") or "Pilot rollback initiated"),
        auth=auth,
        previous_state=before,
        result_state=authority_payload(row),
        risk_level="red",
    )
    return row


def complete_authority(session: Session, row: PilotAuthorityV24, payload: dict[str, Any], auth: AuthContext) -> PilotAuthorityV24:
    require_version(row, int(payload.get("expectedVersion")))
    if row.status != "running":
        raise HTTPException(status_code=409, detail="only a running pilot can be completed")
    gate = gate_for(session, row, row.requested_mode)
    if not gate["eligible"]:
        raise HTTPException(status_code=409, detail={"code": "pilot_completion_blocked", "blockers": gate["blockers"]})
    before = authority_payload(row)
    row.status = "completed"
    row.completed_at = utc_now()
    row.version += 1
    row.updated_at = utc_now()
    run = _pilot_run(session, row)
    run.status = "passed"
    run.ended_at = utc_now()
    run.updated_at = utc_now()
    session.add(run)
    control_ref = "shadow.mode" if row.requested_mode == "shadow" else "pilot.bounded" if row.requested_mode == "bounded_live" else None
    if control_ref:
        control = session.exec(select(ReadinessControl).where(ReadinessControl.control_ref == control_ref)).first()
        if control:
            update_control(session, control_ref, {
                "expectedVersion": control.version,
                "status": "passed",
                "evidenceSummary": _clean(payload.get("reason") or f"Completed {row.requested_mode} pilot {row.authority_ref}"),
                "reason": _clean(payload.get("reason") or "Pilot acceptance completed"),
                "validDays": 180,
            }, auth)
    session.add(row)
    session.flush()
    record_action(
        session,
        row,
        action_type="pilot_completed",
        reason=str(payload.get("reason") or "Pilot completed against acceptance criteria"),
        auth=auth,
        previous_state=before,
        result_state=authority_payload(row),
        risk_level="green",
    )
    return row


def update_uat(session: Session, authority_ref: str, scenario_ref: str, payload: dict[str, Any], auth: AuthContext) -> PilotUATScenarioV24:
    authority = require_authority(session, authority_ref, lock=True)
    scenario = session.exec(
        select(PilotUATScenarioV24)
        .where(PilotUATScenarioV24.authority_ref == authority_ref)
        .where(PilotUATScenarioV24.scenario_ref == scenario_ref)
        .with_for_update()
    ).first()
    if not scenario:
        raise HTTPException(status_code=404, detail="pilot UAT scenario not found")
    expected = int(payload.get("expectedVersion"))
    if scenario.version != expected:
        raise HTTPException(status_code=409, detail={"code": "stale_uat_scenario", "currentVersion": scenario.version})
    status = str(payload.get("status") or "").strip().lower()
    if status not in {"not_run", "passed", "failed", "blocked"}:
        raise HTTPException(status_code=422, detail="invalid UAT status")
    evidence_summary = _clean(payload.get("evidenceSummary"))
    if status in {"passed", "failed", "blocked"} and len(evidence_summary) < 8:
        raise HTTPException(status_code=422, detail="evidenceSummary must contain at least eight characters")
    before = scenario_payload(scenario)
    scenario.status = status
    scenario.evidence_summary = evidence_summary or None
    scenario.tested_by_subject = auth.subject if status != "not_run" else None
    scenario.tested_by_name = auth.actor_name if status != "not_run" else None
    scenario.tested_at = utc_now() if status != "not_run" else None
    scenario.version += 1
    scenario.updated_at = utc_now()
    session.add(scenario)
    session.flush()
    after = scenario_payload(scenario)
    evidence, _ = create_evidence_event(
        session,
        event_type="pilot_uat_result",
        action=f"UAT scenario marked {status}",
        actor_id=auth.actor_id,
        actor_name=auth.actor_name,
        actor_role=auth.role,
        actor_auth_source=auth.auth_source,
        previous_state=before,
        new_state=after,
        reason=str(payload.get("reason") or evidence_summary or "Pilot UAT result recorded"),
        compliance_domain="clinical_governance",
        risk_level="green" if status == "passed" else "red" if status == "failed" else "amber",
        source_module="pilot-control-v24",
        source_record_ref=scenario.scenario_ref,
        correlation_id=authority_ref,
        entity_type="pilot_uat_scenario",
        entity_id=scenario.scenario_ref,
        idempotency_key=f"pilot-uat-v24:{scenario.scenario_ref}:v{scenario.version}",
    )
    if scenario.critical and status in {"failed", "blocked"} and authority.status in {"authorised", "running"}:
        previous_authority = authority_payload(authority)
        authority.status = "blocked"
        authority.version += 1
        authority.updated_at = utc_now()
        authority.evidence_event_ref = evidence.event_ref
        session.add(authority)
        record_action(
            session,
            authority,
            action_type="critical_uat_blocked_pilot",
            reason=str(payload.get("reason") or evidence_summary),
            auth=auth,
            previous_state=previous_authority,
            result_state=authority_payload(authority),
            risk_level="red",
        )
    return scenario


def _canonical_snapshot(row: CanonicalEpisodeState | None, episode_ref: str) -> dict[str, Any]:
    if not row:
        return {"episodeRef": episode_ref, "recorded": False}
    return {
        "episodeRef": row.episode_ref,
        "patientRef": row.patient_ref,
        "patientName": row.patient_name,
        "premisesRef": row.premises_ref,
        "serviceLine": row.service_line,
        "phase": row.phase,
        "status": row.status,
        "ownerRole": row.owner_role,
        "ownerSubject": row.owner_subject,
        "currentAreaRef": row.current_area_ref,
        "nextAction": row.next_action,
        "version": row.version,
        "updatedAt": row.updated_at.isoformat() if row.updated_at else None,
        "recorded": True,
    }


def _compare_shadow(external: dict[str, Any], canonical: dict[str, Any]) -> tuple[list[str], str]:
    if not canonical.get("recorded"):
        return ["unknown_canonical_episode"], "red"
    mismatches: list[str] = []
    patient = external.get("patientRef")
    if patient and canonical.get("patientRef") and str(patient) != str(canonical.get("patientRef")):
        mismatches.append("patient_identity_mismatch")
    phase = external.get("phase", external.get("stage"))
    if phase and str(phase).lower() != str(canonical.get("phase") or "").lower():
        mismatches.append("phase_mismatch")
    area = external.get("currentAreaRef", external.get("areaRef", external.get("room")))
    if area and str(area).lower() != str(canonical.get("currentAreaRef") or "").lower():
        mismatches.append("area_mismatch")
    owner_role = external.get("ownerRole")
    if owner_role and str(owner_role).lower() != str(canonical.get("ownerRole") or "").lower():
        mismatches.append("owner_role_mismatch")
    status = external.get("status")
    if status and str(status).lower() != str(canonical.get("status") or "").lower():
        mismatches.append("status_mismatch")
    severity = "red" if {"unknown_canonical_episode", "patient_identity_mismatch"} & set(mismatches) else "amber" if mismatches else "green"
    return mismatches, severity


def import_shadow_comparisons(session: Session, row: PilotAuthorityV24, payload: dict[str, Any], auth: AuthContext) -> list[PilotShadowComparisonV24]:
    if row.requested_mode not in {"shadow", "bounded_live"}:
        raise HTTPException(status_code=409, detail="shadow comparisons require a shadow or bounded-live pilot plan")
    incoming_rows = list(payload.get("rows") or [])
    if not incoming_rows:
        raise HTTPException(status_code=422, detail="at least one shadow comparison row is required")
    before_count = len(session.exec(select(PilotShadowComparisonV24).where(PilotShadowComparisonV24.authority_ref == row.authority_ref)).all())
    output: list[PilotShadowComparisonV24] = []
    for incoming in incoming_rows:
        external_ref = _clean(incoming.get("externalRef"), 200)
        episode_ref = _clean(incoming.get("canonicalEpisodeRef"), 200)
        if not external_ref or not episode_ref:
            raise HTTPException(status_code=422, detail="externalRef and canonicalEpisodeRef are required")
        episode = session.exec(select(CanonicalEpisodeState).where(CanonicalEpisodeState.episode_ref == episode_ref)).first()
        canonical = _canonical_snapshot(episode, episode_ref)
        external = dict(incoming.get("externalSnapshot") or {})
        mismatches, severity = _compare_shadow(external, canonical)
        comparison = session.exec(
            select(PilotShadowComparisonV24)
            .where(PilotShadowComparisonV24.authority_ref == row.authority_ref)
            .where(PilotShadowComparisonV24.external_ref == external_ref)
            .with_for_update()
        ).first()
        if comparison:
            comparison.canonical_episode_ref = episode_ref
            comparison.patient_ref = episode.patient_ref if episode else None
            comparison.source_system = _clean(incoming.get("sourceSystem") or comparison.source_system, 160)
            comparison.external_snapshot = external
            comparison.canonical_snapshot = canonical
            comparison.mismatch_codes = mismatches
            comparison.severity = severity
            comparison.status = "matched" if not mismatches else "mismatch"
            comparison.reviewed_by_subject = None
            comparison.reviewed_by_name = None
            comparison.review_note = None
            comparison.reviewed_at = None
            comparison.version += 1
            comparison.updated_at = utc_now()
        else:
            comparison = PilotShadowComparisonV24(
                comparison_ref=new_ref("pilot-shadow-v24"),
                authority_ref=row.authority_ref,
                external_ref=external_ref,
                canonical_episode_ref=episode_ref,
                patient_ref=episode.patient_ref if episode else None,
                source_system=_clean(incoming.get("sourceSystem") or "external_shadow_source", 160),
                external_snapshot=external,
                canonical_snapshot=canonical,
                mismatch_codes=mismatches,
                severity=severity,
                status="matched" if not mismatches else "mismatch",
            )
        session.add(comparison)
        output.append(comparison)
    session.flush()
    record_action(
        session,
        row,
        action_type="shadow_comparisons_imported",
        reason=str(payload.get("reason") or "Import canonical shadow comparison evidence"),
        auth=auth,
        previous_state={"status": row.status, "comparisonCount": before_count},
        result_state={
            "status": row.status,
            "comparisonCount": before_count + len(output),
            "imported": len(output),
            "red": len([item for item in output if item.severity == "red"]),
            "amber": len([item for item in output if item.severity == "amber"]),
        },
    )
    return output


def review_shadow_comparison(session: Session, row: PilotAuthorityV24, comparison_ref: str, payload: dict[str, Any], auth: AuthContext) -> PilotShadowComparisonV24:
    comparison = session.exec(
        select(PilotShadowComparisonV24)
        .where(PilotShadowComparisonV24.authority_ref == row.authority_ref)
        .where(PilotShadowComparisonV24.comparison_ref == comparison_ref)
        .with_for_update()
    ).first()
    if not comparison:
        raise HTTPException(status_code=404, detail="shadow comparison not found")
    expected = int(payload.get("expectedVersion"))
    if comparison.version != expected:
        raise HTTPException(status_code=409, detail={"code": "stale_shadow_comparison", "currentVersion": comparison.version})
    decision = str(payload.get("decision") or "").strip().lower()
    if decision not in {"approved", "rejected"}:
        raise HTTPException(status_code=422, detail="decision must be approved or rejected")
    note = _clean(payload.get("note"))
    if len(note) < 8:
        raise HTTPException(status_code=422, detail="review note must contain at least eight characters")
    before = comparison_payload(comparison)
    comparison.status = decision
    comparison.reviewed_by_subject = auth.subject
    comparison.reviewed_by_name = auth.actor_name
    comparison.review_note = note
    comparison.reviewed_at = utc_now()
    comparison.version += 1
    comparison.updated_at = utc_now()
    session.add(comparison)
    session.flush()
    evidence, _ = create_evidence_event(
        session,
        event_type="pilot_shadow_comparison_review",
        action=f"shadow comparison {decision}",
        actor_id=auth.actor_id,
        actor_name=auth.actor_name,
        actor_role=auth.role,
        actor_auth_source=auth.auth_source,
        previous_state=before,
        new_state=comparison_payload(comparison),
        reason=note,
        compliance_domain="clinical_governance",
        risk_level="red" if comparison.severity == "red" else "amber",
        source_module="pilot-control-v24",
        source_record_ref=comparison.comparison_ref,
        correlation_id=row.authority_ref,
        entity_type="pilot_shadow_comparison",
        entity_id=comparison.comparison_ref,
        idempotency_key=f"pilot-shadow-review-v24:{comparison.comparison_ref}:v{comparison.version}",
    )
    row.evidence_event_ref = evidence.event_ref
    row.updated_at = utc_now()
    session.add(row)
    return comparison


def command_state(session: Session, row: PilotAuthorityV24) -> dict[str, Any]:
    run = _pilot_run(session, row)
    approvals = session.exec(
        select(PilotApprovalV24)
        .where(PilotApprovalV24.authority_ref == row.authority_ref)
        .order_by(PilotApprovalV24.created_at.desc())
        .limit(100)
    ).all()
    actions = session.exec(
        select(PilotControlActionV24)
        .where(PilotControlActionV24.authority_ref == row.authority_ref)
        .order_by(PilotControlActionV24.created_at.desc())
        .limit(200)
    ).all()
    comparisons = session.exec(
        select(PilotShadowComparisonV24)
        .where(PilotShadowComparisonV24.authority_ref == row.authority_ref)
        .order_by(PilotShadowComparisonV24.created_at.desc())
        .limit(1000)
    ).all()
    scenarios = seed_uat_scenarios(session, row.authority_ref)
    observations = session.exec(
        select(PilotObservation)
        .where(PilotObservation.run_ref == row.run_ref)
        .order_by(PilotObservation.created_at.desc())
        .limit(500)
    ).all()
    return {
        "authority": authority_payload(row),
        "pilotRun": pilot_dict(run),
        "gate": gate_for(session, row),
        "approvals": [approval_payload(item) for item in approvals],
        "actions": [action_payload(item) for item in actions],
        "shadowComparisons": [comparison_payload(item) for item in comparisons],
        "uatScenarios": [scenario_payload(item) for item in scenarios],
        "observations": [{
            "observationRef": item.observation_ref,
            "severity": item.severity,
            "category": item.category,
            "summary": item.summary,
            "expectedBehaviour": item.expected_behaviour,
            "actualBehaviour": item.actual_behaviour,
            "ownerRole": item.owner_role,
            "status": item.status,
            "resolution": item.resolution,
            "createdAt": item.created_at.isoformat(),
            "resolvedAt": item.resolved_at.isoformat() if item.resolved_at else None,
        } for item in observations],
        "authorityBoundary": {
            "permitted": [
                "synthetic validation",
                "shadow comparison against canonical recorded state",
                "bounded workflow pilot under named human authority",
                "owned operational review work",
                "immediate stop and governed rollback",
            ],
            "forbidden": [
                "autonomous diagnosis",
                "autonomous prescribing or dose change",
                "medication administration",
                "automatic result acknowledgement",
                "fabricated consent or evidence completion",
                "automatic admission, discharge or clinical phase transition",
            ],
        },
    }


def list_authorities(session: Session, premises_ref: str | None = None) -> list[dict[str, Any]]:
    query = select(PilotAuthorityV24).order_by(PilotAuthorityV24.created_at.desc())
    if premises_ref:
        query = query.where(PilotAuthorityV24.premises_ref == premises_ref)
    rows = session.exec(query.limit(200)).all()
    return [
        {
            "authority": authority_payload(row),
            "gate": gate_for(session, row),
        }
        for row in rows
    ]
