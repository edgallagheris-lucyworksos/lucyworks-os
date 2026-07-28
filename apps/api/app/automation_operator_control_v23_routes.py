from __future__ import annotations

from datetime import date
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field as PydanticField
from sqlmodel import Session, select

from app.auth import AuthContext, CLINICAL_ROLES, SENIOR_ROLES, require_authenticated, require_roles
from app.automation_operator_control_v23_models import AutomationOperatorActionV23
from app.database import get_session
from app.evidence_service import create_evidence_event
from app.event_driven_automation_v22_models import AutomationRuntimeConfigV22, AutomationTriggerV22
from app.event_driven_automation_v22_service import (
    SUPPORTED_MODES,
    SUPPORTED_SOURCE_TYPES,
    dry_run_episode,
    process_trigger,
    runtime_settings,
    scan_and_dispatch,
)
from app.models import WorkItem
from app.operational_automation_v20_models import AutomationDecisionV20
from app.operational_automation_v20_routes import AUTOMATION_ROLES


router = APIRouter(prefix="/api/v23/automation", tags=["automation-operator-control-v23"])
GOVERNED_ACKNOWLEDGEMENT = "AUTHORISE GOVERNED AUTOMATION"


class ServiceValidationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: str
    enabledTriggerTypes: list[str] = PydanticField(default_factory=lambda: sorted(SUPPORTED_SOURCE_TYPES))
    serviceSubject: str = PydanticField(min_length=3, max_length=200)
    serviceName: str = PydanticField(min_length=3, max_length=200)
    serviceRole: str = PydanticField(min_length=3, max_length=80)


class OperatorConfigUpdate(ServiceValidationRequest):
    backgroundScanEnabled: bool = False
    scanIntervalSeconds: int = PydanticField(default=60, ge=30, le=3600)
    expectedVersion: int = PydanticField(default=0, ge=0)
    reason: str = PydanticField(min_length=8, max_length=2000)
    acknowledgement: str | None = PydanticField(default=None, max_length=200)


class ReasonedAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = PydanticField(min_length=8, max_length=2000)


class ReconcileRequest(ReasonedAction):
    premisesRef: str = PydanticField(min_length=1, max_length=160)
    operationalDate: date | None = None
    episodeRef: str | None = PydanticField(default=None, max_length=160)
    sourceTypes: list[str] = PydanticField(default_factory=lambda: sorted(SUPPORTED_SOURCE_TYPES))


def new_ref(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def validate_service_configuration(
    *,
    mode: str,
    enabled_trigger_types: list[str],
    service_subject: str,
    service_name: str,
    service_role: str,
) -> dict[str, Any]:
    normal_mode = mode.strip().lower()
    trigger_types = list(dict.fromkeys(value.strip().lower() for value in enabled_trigger_types if value.strip()))
    role = service_role.strip().lower()
    subject = service_subject.strip()
    name = service_name.strip()
    checks = [
        {"code": "mode_supported", "passed": normal_mode in SUPPORTED_MODES, "detail": "Operating mode is recognised."},
        {"code": "source_types_supported", "passed": not (set(trigger_types) - SUPPORTED_SOURCE_TYPES), "detail": "All enabled trigger types use recorded-source evaluators."},
        {"code": "service_subject_recorded", "passed": len(subject) >= 3, "detail": "A stable internal service subject is recorded."},
        {"code": "service_name_recorded", "passed": len(name) >= 3, "detail": "A visible service identity name is recorded."},
        {"code": "service_role_permitted", "passed": role in AUTOMATION_ROLES, "detail": "The configured role is permitted to request governed automation evaluation."},
    ]
    clinical_enabled = bool({"observation", "critical_result"} & set(trigger_types))
    checks.append({
        "code": "clinical_role_for_clinical_sources",
        "passed": not (normal_mode == "governed_commit" and clinical_enabled) or role in CLINICAL_ROLES,
        "detail": "Governed clinical-source evaluation requires a mapped clinical service role.",
    })
    valid = all(bool(item["passed"]) for item in checks)
    return {
        "valid": valid,
        "mode": normal_mode,
        "enabledTriggerTypes": trigger_types,
        "serviceSubject": subject,
        "serviceName": name,
        "serviceRole": role,
        "identitySource": "configured_internal_service_identity",
        "clinicalSourcesEnabled": clinical_enabled,
        "checks": checks,
        "authorityBoundary": "May request accountable human-owned review or coordination work only.",
        "forbiddenEffects": [
            "diagnosis",
            "prescription",
            "dose_change",
            "medication_administration",
            "result_acknowledgement",
            "evidence_completion",
            "automatic_rescheduling",
            "admission",
            "discharge",
            "clinical_phase_transition",
        ],
    }


def configuration_payload(settings: dict[str, Any]) -> dict[str, Any]:
    return {
        "configRef": settings.get("configRef"),
        "premisesRef": settings.get("premisesRef"),
        "mode": settings.get("mode", "disabled"),
        "enabledTriggerTypes": list(settings.get("enabledTriggerTypes") or []),
        "serviceSubject": settings.get("serviceSubject"),
        "serviceName": settings.get("serviceName"),
        "serviceRole": settings.get("serviceRole"),
        "backgroundScanEnabled": bool(settings.get("backgroundScanEnabled")),
        "scanIntervalSeconds": int(settings.get("scanIntervalSeconds") or 60),
        "version": int(settings.get("version") or 0),
        "persisted": bool(settings.get("persisted")),
    }


def work_item_payload(row: WorkItem) -> dict[str, Any]:
    return {
        "id": row.id,
        "title": row.title,
        "description": row.description,
        "category": row.category,
        "urgency": row.urgency,
        "ownerRole": row.owner_role,
        "status": row.status,
        "episodeRef": row.linked_episode_ref,
        "patientName": row.linked_patient_name,
        "sectionName": row.section_name,
        "roomName": row.room_name,
        "dueAt": row.due_at.isoformat() if row.due_at else None,
        "source": row.source,
    }


def decision_payload(row: AutomationDecisionV20 | None) -> dict[str, Any] | None:
    if not row:
        return None
    return {
        "decisionRef": row.decision_ref,
        "outcome": row.outcome,
        "commitRequested": row.commit_requested,
        "committed": row.committed,
        "replayed": row.replayed,
        "proposals": list(row.proposals),
        "actorSubject": row.actor_subject,
        "actorName": row.actor_name,
        "actorRole": row.actor_role,
        "actorAuthSource": row.actor_auth_source,
        "reason": row.reason,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
        "evidenceEventRef": row.evidence_event_ref,
    }


def trigger_payload(
    row: AutomationTriggerV22,
    *,
    work_by_id: dict[int, WorkItem],
    decisions_by_ref: dict[str, AutomationDecisionV20],
) -> dict[str, Any]:
    work = [work_by_id[value] for value in row.work_item_ids if value in work_by_id]
    return {
        "triggerRef": row.trigger_ref,
        "premisesRef": row.premises_ref,
        "episodeRef": row.episode_ref,
        "sourceType": row.source_type,
        "sourceRef": row.source_ref,
        "sourceVersion": row.source_version,
        "sourceStateHash": row.source_state_hash,
        "sourceSnapshot": row.source_snapshot,
        "mode": row.mode,
        "status": row.status,
        "attempts": row.attempts,
        "decisionRef": row.decision_ref,
        "decisionOutcome": row.decision_outcome,
        "decision": decision_payload(decisions_by_ref.get(row.decision_ref or "")),
        "workItems": [work_item_payload(item) for item in work],
        "initiatedBy": {
            "subject": row.initiated_by_subject,
            "name": row.initiated_by_name,
            "role": row.initiated_by_role,
        },
        "errorCode": row.error_code,
        "errorDetail": row.error_detail,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
        "startedAt": row.started_at.isoformat() if row.started_at else None,
        "processedAt": row.processed_at.isoformat() if row.processed_at else None,
    }


def enrich_triggers(session: Session, rows: list[AutomationTriggerV22]) -> list[dict[str, Any]]:
    work_ids = sorted({value for row in rows for value in row.work_item_ids})
    decision_refs = sorted({row.decision_ref for row in rows if row.decision_ref})
    work_rows = session.exec(select(WorkItem).where(WorkItem.id.in_(work_ids))).all() if work_ids else []
    decision_rows = session.exec(
        select(AutomationDecisionV20).where(AutomationDecisionV20.decision_ref.in_(decision_refs))
    ).all() if decision_refs else []
    work_by_id = {int(row.id): row for row in work_rows if row.id is not None}
    decisions_by_ref = {row.decision_ref: row for row in decision_rows}
    return [trigger_payload(row, work_by_id=work_by_id, decisions_by_ref=decisions_by_ref) for row in rows]


def action_payload(row: AutomationOperatorActionV23) -> dict[str, Any]:
    return {
        "actionRef": row.action_ref,
        "actionType": row.action_type,
        "premisesRef": row.premises_ref,
        "episodeRef": row.episode_ref,
        "targetType": row.target_type,
        "targetRef": row.target_ref,
        "reason": row.reason,
        "acknowledgement": row.acknowledgement,
        "previousState": row.previous_state,
        "resultState": row.result_state,
        "actor": {
            "subject": row.actor_subject,
            "name": row.actor_name,
            "role": row.actor_role,
            "authSource": row.actor_auth_source,
        },
        "evidenceEventRef": row.evidence_event_ref,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
    }


def record_operator_action(
    session: Session,
    *,
    action_type: str,
    premises_ref: str,
    target_type: str,
    target_ref: str,
    reason: str,
    auth: AuthContext,
    previous_state: dict[str, Any],
    result_state: dict[str, Any],
    episode_ref: str | None = None,
    acknowledgement: str | None = None,
) -> AutomationOperatorActionV23:
    row = AutomationOperatorActionV23(
        action_ref=new_ref("autoaction-v23"),
        action_type=action_type,
        premises_ref=premises_ref,
        episode_ref=episode_ref,
        target_type=target_type,
        target_ref=target_ref,
        reason=reason.strip(),
        acknowledgement=acknowledgement.strip() if acknowledgement else None,
        previous_state=previous_state,
        result_state=result_state,
        actor_subject=auth.subject,
        actor_name=auth.actor_name,
        actor_role=auth.role,
        actor_auth_source=auth.auth_source,
    )
    session.add(row)
    session.flush()
    evidence, _ = create_evidence_event(
        session,
        event_type=f"automation_operator_{action_type}",
        action=action_type,
        referral_episode_id=episode_ref,
        actor_id=auth.actor_id,
        actor_name=auth.actor_name,
        actor_role=auth.role,
        actor_auth_source=auth.auth_source,
        previous_state=previous_state,
        new_state=result_state,
        reason=reason,
        compliance_domain="clinical_governance" if action_type == "configuration_changed" else "operations",
        risk_level="amber",
        source_module="automation-operator-control-v23",
        source_record_ref=row.action_ref,
        correlation_id=episode_ref or premises_ref,
        entity_type=target_type,
        entity_id=target_ref,
        idempotency_key=f"automation-operator-v23:{row.action_ref}",
    )
    row.evidence_event_ref = evidence.event_ref
    session.add(row)
    return row


def control_state(session: Session, premises_ref: str) -> dict[str, Any]:
    configuration = configuration_payload(runtime_settings(session, premises_ref))
    validation = validate_service_configuration(
        mode=str(configuration["mode"]),
        enabled_trigger_types=list(configuration["enabledTriggerTypes"]),
        service_subject=str(configuration["serviceSubject"] or ""),
        service_name=str(configuration["serviceName"] or ""),
        service_role=str(configuration["serviceRole"] or ""),
    )
    triggers = session.exec(
        select(AutomationTriggerV22)
        .where(AutomationTriggerV22.premises_ref == premises_ref)
        .order_by(AutomationTriggerV22.created_at.desc())
        .limit(1000)
    ).all()
    actions = session.exec(
        select(AutomationOperatorActionV23)
        .where(AutomationOperatorActionV23.premises_ref == premises_ref)
        .order_by(AutomationOperatorActionV23.created_at.desc())
        .limit(50)
    ).all()
    return {
        "configuration": configuration,
        "serviceValidation": validation,
        "summary": {
            "triggers": len(triggers),
            "failed": sum(1 for row in triggers if row.status == "failed"),
            "queued": sum(1 for row in triggers if row.status in {"queued", "processing"}),
            "completed": sum(1 for row in triggers if row.status == "completed"),
            "previewed": sum(1 for row in triggers if row.status == "previewed"),
            "skipped": sum(1 for row in triggers if row.status == "skipped"),
            "workItems": sum(len(row.work_item_ids) for row in triggers),
        },
        "recentActions": [action_payload(row) for row in actions],
        "governedAcknowledgement": GOVERNED_ACKNOWLEDGEMENT,
    }


@router.get("/control/{premises_ref}")
def get_control_state(
    premises_ref: str,
    session: Session = Depends(get_session),
    _: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    return control_state(session, premises_ref)


@router.post("/validate-service")
def validate_prospective_service(
    payload: ServiceValidationRequest,
    _: AuthContext = Depends(require_roles(*SENIOR_ROLES)),
) -> dict[str, Any]:
    return validate_service_configuration(
        mode=payload.mode,
        enabled_trigger_types=payload.enabledTriggerTypes,
        service_subject=payload.serviceSubject,
        service_name=payload.serviceName,
        service_role=payload.serviceRole,
    )


@router.put("/control/{premises_ref}")
def update_control_state(
    premises_ref: str,
    payload: OperatorConfigUpdate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*SENIOR_ROLES)),
) -> dict[str, Any]:
    validation = validate_service_configuration(
        mode=payload.mode,
        enabled_trigger_types=payload.enabledTriggerTypes,
        service_subject=payload.serviceSubject,
        service_name=payload.serviceName,
        service_role=payload.serviceRole,
    )
    if not validation["valid"]:
        raise HTTPException(status_code=422, detail={"code": "service_configuration_invalid", "validation": validation})
    if validation["mode"] == "governed_commit" and (payload.acknowledgement or "").strip() != GOVERNED_ACKNOWLEDGEMENT:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "governed_acknowledgement_required",
                "requiredAcknowledgement": GOVERNED_ACKNOWLEDGEMENT,
            },
        )

    before = configuration_payload(runtime_settings(session, premises_ref))
    row = session.exec(
        select(AutomationRuntimeConfigV22).where(AutomationRuntimeConfigV22.premises_ref == premises_ref)
    ).first()
    if row:
        if payload.expectedVersion != row.version:
            raise HTTPException(status_code=409, detail={"code": "stale_configuration", "currentVersion": row.version})
        row.version += 1
    else:
        if payload.expectedVersion != 0:
            raise HTTPException(status_code=409, detail={"code": "stale_configuration", "currentVersion": 0})
        row = AutomationRuntimeConfigV22(config_ref=new_ref("autoconfig-v23"), premises_ref=premises_ref)

    row.mode = str(validation["mode"])
    row.enabled_trigger_types = list(validation["enabledTriggerTypes"])
    row.service_subject = str(validation["serviceSubject"])
    row.service_name = str(validation["serviceName"])
    row.service_role = str(validation["serviceRole"])
    row.background_scan_enabled = payload.backgroundScanEnabled
    row.scan_interval_seconds = payload.scanIntervalSeconds
    row.updated_by_subject = auth.subject
    row.updated_by_name = auth.actor_name
    from app.event_driven_automation_v22_service import utc_now
    row.updated_at = utc_now()
    session.add(row)
    session.flush()

    after = configuration_payload({
        "configRef": row.config_ref,
        "premisesRef": row.premises_ref,
        "mode": row.mode,
        "enabledTriggerTypes": row.enabled_trigger_types,
        "serviceSubject": row.service_subject,
        "serviceName": row.service_name,
        "serviceRole": row.service_role,
        "backgroundScanEnabled": row.background_scan_enabled,
        "scanIntervalSeconds": row.scan_interval_seconds,
        "version": row.version,
        "persisted": True,
    })
    action = record_operator_action(
        session,
        action_type="configuration_changed",
        premises_ref=premises_ref,
        target_type="automation_runtime_configuration",
        target_ref=row.config_ref,
        reason=payload.reason,
        acknowledgement=payload.acknowledgement,
        auth=auth,
        previous_state=before,
        result_state={"configuration": after, "serviceValidation": validation},
    )
    session.commit()
    session.refresh(row)
    session.refresh(action)
    result = control_state(session, premises_ref)
    result["operatorAction"] = action_payload(action)
    return result


@router.get("/overview")
def get_operator_overview(
    premises_ref: str = "default-premises",
    episode_ref: str | None = None,
    source_type: str | None = None,
    status: str | None = None,
    operational_date: date | None = None,
    limit: int = Query(default=300, ge=1, le=1000),
    session: Session = Depends(get_session),
    _: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    query = select(AutomationTriggerV22).where(AutomationTriggerV22.premises_ref == premises_ref)
    if episode_ref:
        query = query.where(AutomationTriggerV22.episode_ref == episode_ref)
    if source_type:
        normal_source = source_type.strip().lower()
        if normal_source not in SUPPORTED_SOURCE_TYPES:
            raise HTTPException(status_code=422, detail="unsupported source_type")
        query = query.where(AutomationTriggerV22.source_type == normal_source)
    if status:
        query = query.where(AutomationTriggerV22.status == status.strip().lower())
    rows = session.exec(query.order_by(AutomationTriggerV22.created_at.desc()).limit(limit)).all()
    if operational_date:
        date_text = operational_date.isoformat()
        rows = [
            row for row in rows
            if row.source_type != "operational_delay"
            or str(row.source_snapshot.get("startsAt") or "").startswith(date_text)
        ]
    triggers = enrich_triggers(session, rows)
    return {
        "premisesRef": premises_ref,
        "configuration": configuration_payload(runtime_settings(session, premises_ref)),
        "summary": {
            "count": len(triggers),
            "failed": sum(1 for row in rows if row.status == "failed"),
            "active": sum(1 for row in rows if row.status in {"queued", "processing"}),
            "workItems": sum(len(row.work_item_ids) for row in rows),
        },
        "triggers": triggers,
    }


@router.get("/episodes/{episode_ref}/history")
def get_episode_history(
    episode_ref: str,
    session: Session = Depends(get_session),
    _: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    rows = session.exec(
        select(AutomationTriggerV22)
        .where(AutomationTriggerV22.episode_ref == episode_ref)
        .order_by(AutomationTriggerV22.created_at.desc())
        .limit(500)
    ).all()
    return {
        "episodeRef": episode_ref,
        "triggers": enrich_triggers(session, rows),
        "failedCount": sum(1 for row in rows if row.status == "failed"),
        "workItemCount": sum(len(row.work_item_ids) for row in rows),
    }


@router.get("/blocks/{block_ref}/history")
def get_block_history(
    block_ref: str,
    session: Session = Depends(get_session),
    _: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    rows = session.exec(
        select(AutomationTriggerV22)
        .where(AutomationTriggerV22.source_type == "operational_delay")
        .where(AutomationTriggerV22.source_ref == block_ref)
        .order_by(AutomationTriggerV22.created_at.desc())
        .limit(100)
    ).all()
    return {
        "blockRef": block_ref,
        "triggers": enrich_triggers(session, rows),
        "latest": enrich_triggers(session, rows[:1])[0] if rows else None,
    }


@router.post("/episodes/{episode_ref}/dry-run")
def run_episode_dry_run(
    episode_ref: str,
    payload: ReasonedAction,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*SENIOR_ROLES)),
) -> dict[str, Any]:
    result = dry_run_episode(episode_ref)
    action = record_operator_action(
        session,
        action_type="episode_dry_run",
        premises_ref=str(result["premisesRef"]),
        episode_ref=episode_ref,
        target_type="canonical_episode",
        target_ref=episode_ref,
        reason=payload.reason,
        auth=auth,
        previous_state={},
        result_state={
            "proposalCount": result["proposalCount"],
            "sourceCount": len(result["sources"]),
            "workCreated": False,
        },
    )
    session.commit()
    session.refresh(action)
    return {**result, "operatorAction": action_payload(action)}


@router.post("/reconcile")
def reconcile_recorded_sources(
    payload: ReconcileRequest,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*SENIOR_ROLES)),
) -> dict[str, Any]:
    source_types = {value.strip().lower() for value in payload.sourceTypes}
    unknown = source_types - SUPPORTED_SOURCE_TYPES
    if unknown:
        raise HTTPException(status_code=422, detail=f"unsupported source types: {', '.join(sorted(unknown))}")
    rows = scan_and_dispatch(
        premises_ref=payload.premisesRef,
        operational_date=payload.operationalDate,
        episode_ref=payload.episodeRef,
        source_types=source_types,
        initiated_by=auth,
    )
    summary = {
        "count": len(rows),
        "failedCount": sum(1 for row in rows if row.status == "failed"),
        "workItemCount": sum(len(row.work_item_ids) for row in rows),
        "triggerRefs": [row.trigger_ref for row in rows],
    }
    action = record_operator_action(
        session,
        action_type="reconciliation_scan",
        premises_ref=payload.premisesRef,
        episode_ref=payload.episodeRef,
        target_type="automation_source_scope",
        target_ref=payload.episodeRef or (payload.operationalDate.isoformat() if payload.operationalDate else payload.premisesRef),
        reason=payload.reason,
        auth=auth,
        previous_state={"sourceTypes": sorted(source_types)},
        result_state=summary,
    )
    session.commit()
    session.refresh(action)
    return {**summary, "triggers": [row.trigger_ref for row in rows], "operatorAction": action_payload(action)}


@router.post("/triggers/{trigger_ref}/retry")
def retry_failed_trigger(
    trigger_ref: str,
    payload: ReasonedAction,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*SENIOR_ROLES)),
) -> dict[str, Any]:
    before_row = session.exec(
        select(AutomationTriggerV22).where(AutomationTriggerV22.trigger_ref == trigger_ref)
    ).first()
    if not before_row:
        raise HTTPException(status_code=404, detail="automation trigger not found")
    before = {
        "status": before_row.status,
        "attempts": before_row.attempts,
        "errorCode": before_row.error_code,
        "errorDetail": before_row.error_detail,
    }
    result_row = process_trigger(trigger_ref, force=True)
    result = {
        "status": result_row.status,
        "attempts": result_row.attempts,
        "decisionRef": result_row.decision_ref,
        "decisionOutcome": result_row.decision_outcome,
        "workItemIds": list(result_row.work_item_ids),
        "errorCode": result_row.error_code,
        "errorDetail": result_row.error_detail,
    }
    action = record_operator_action(
        session,
        action_type="trigger_retry",
        premises_ref=result_row.premises_ref,
        episode_ref=result_row.episode_ref,
        target_type="automation_trigger",
        target_ref=trigger_ref,
        reason=payload.reason,
        auth=auth,
        previous_state=before,
        result_state=result,
    )
    session.commit()
    session.refresh(action)
    refreshed = session.exec(
        select(AutomationTriggerV22).where(AutomationTriggerV22.trigger_ref == trigger_ref)
    ).one()
    return {
        "trigger": enrich_triggers(session, [refreshed])[0],
        "operatorAction": action_payload(action),
    }
