from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.auth import CLINICAL_ROLES, SENIOR_ROLES, AuthContext, require_authenticated
from app.control_plane_routes import CriticalResultCreate, CriticalResultDecision, HandoverCreate, HandoverDecision
from app.database import get_session
from app.operational_context_v26_models import CanonicalCommandV26, LegacyRouteConvergenceV26, OrganisationV26, SiteV26
from app.operating_context_v26_service import memberships_for, resolve_context, switch_context
from app.operational_command_v26_service import (
    CLINICAL_COMMANDS,
    SENIOR_COMMANDS,
    active_impacts,
    command_dict,
    impact_dict,
    record_command,
    seed_legacy_routes,
    update_linked_command,
)
from app.patient_care_routes import EpisodeStatePatch
from app.safety_bridge_v25_routes import (
    secure_acknowledge_critical_result as v25_acknowledge_critical_result,
    secure_create_critical_result as v25_create_critical_result,
    secure_create_handover as v25_create_handover,
    secure_decide_handover as v25_decide_handover,
    secure_update_episode_state as v25_update_episode_state,
)

router = APIRouter(tags=["operational-convergence-v26"])


class ContextSwitchRequest(BaseModel):
    siteRef: str
    expectedVersion: int
    reason: str = Field(min_length=3, max_length=500)


class CanonicalCommandRequest(BaseModel):
    commandType: str
    payload: dict[str, Any] = Field(default_factory=dict)
    sourceRecordRef: str | None = None
    idempotencyKey: str | None = None


def _require_command_role(command_type: str, auth: AuthContext) -> None:
    if command_type in CLINICAL_COMMANDS and auth.role not in CLINICAL_ROLES | SENIOR_ROLES:
        raise HTTPException(status_code=403, detail="clinical or senior role required for this command")
    if command_type in SENIOR_COMMANDS and auth.role not in SENIOR_ROLES:
        raise HTTPException(status_code=403, detail="senior role required for this command")


def _context_payload(session: Session, auth: AuthContext) -> dict[str, Any]:
    context = resolve_context(session, auth)
    memberships = memberships_for(session, auth)
    sites = {
        row.site_ref: session.exec(select(SiteV26).where(SiteV26.site_ref == row.site_ref)).first()
        for row in memberships
    }
    organisation_refs = sorted({row.organisation_ref for row in memberships})
    organisations = session.exec(
        select(OrganisationV26).where(OrganisationV26.organisation_ref.in_(organisation_refs))
    ).all() if organisation_refs else []
    return {
        "context": context.as_dict(),
        "organisations": [
            {"organisationRef": row.organisation_ref, "name": row.name, "status": row.status}
            for row in organisations
        ],
        "sites": [
            {
                "membershipRef": row.membership_ref,
                "organisationRef": row.organisation_ref,
                "siteRef": row.site_ref,
                "premisesRef": row.premises_ref,
                "name": sites[row.site_ref].name if sites.get(row.site_ref) else row.site_ref,
                "timezone": sites[row.site_ref].timezone_name if sites.get(row.site_ref) else "Europe/London",
                "configurationState": sites[row.site_ref].configuration_state if sites.get(row.site_ref) else "unknown",
                "role": row.role,
                "isPrimary": row.is_primary,
            }
            for row in memberships
        ],
    }


@router.get("/api/v26/context")
def current_operating_context(
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    payload = _context_payload(session, auth)
    seed_legacy_routes(session)
    session.commit()
    return payload


@router.post("/api/v26/context/switch")
def change_operating_context(
    payload: ContextSwitchRequest,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    context, evidence = switch_context(
        session,
        auth,
        site_ref=payload.siteRef,
        expected_version=payload.expectedVersion,
        reason=payload.reason,
    )
    session.commit()
    return {
        "context": context.as_dict(),
        "switch": {
            "switchRef": evidence.switch_ref,
            "previousContext": evidence.previous_context,
            "newContext": evidence.new_context,
            "reason": evidence.reason,
            "evidenceEventRef": evidence.evidence_event_ref,
            "createdAt": evidence.created_at.isoformat(),
        },
    }


@router.post("/api/v26/commands")
def create_canonical_command(
    request: CanonicalCommandRequest,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    command_type = request.commandType.strip().lower()
    _require_command_role(command_type, auth)
    context = resolve_context(session, auth)
    row, safety, created = record_command(
        session,
        auth,
        context,
        command_type=command_type,
        payload=request.payload,
        source_route="/api/v26/commands",
        source_module="operational-convergence-v26",
        source_record_ref=request.sourceRecordRef,
        idempotency_key=request.idempotencyKey,
    )
    seed_legacy_routes(session)
    session.commit()
    session.refresh(row)
    return {"command": command_dict(row), "safetyRecord": safety, "created": created, "context": context.as_dict()}


@router.get("/api/v26/commands")
def list_canonical_commands(
    status: str | None = Query(default=None),
    patientRef: str | None = Query(default=None),
    episodeRef: str | None = Query(default=None),
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    context = resolve_context(session, auth)
    query = select(CanonicalCommandV26).where(
        CanonicalCommandV26.organisation_ref == context.organisation_ref,
        CanonicalCommandV26.site_ref == context.site_ref,
        CanonicalCommandV26.premises_ref == context.premises_ref,
    )
    if status:
        query = query.where(CanonicalCommandV26.status == status)
    if patientRef:
        query = query.where(CanonicalCommandV26.patient_ref == patientRef)
    if episodeRef:
        query = query.where(CanonicalCommandV26.episode_ref == episodeRef)
    rows = session.exec(query.order_by(CanonicalCommandV26.created_at.desc())).all()
    session.commit()
    return {"context": context.as_dict(), "commands": [command_dict(row) for row in rows]}


@router.get("/api/v26/operational-view")
def operational_view(
    patientRef: str | None = Query(default=None),
    episodeRef: str | None = Query(default=None),
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    context = resolve_context(session, auth)
    impacts = active_impacts(session, context, patient_ref=patientRef, episode_ref=episodeRef)
    commands = session.exec(select(CanonicalCommandV26).where(
        CanonicalCommandV26.organisation_ref == context.organisation_ref,
        CanonicalCommandV26.site_ref == context.site_ref,
        CanonicalCommandV26.premises_ref == context.premises_ref,
        CanonicalCommandV26.status.notin_(["completed", "closed", "cancelled"]),
    ).order_by(CanonicalCommandV26.created_at.desc())).all()
    severity_counts: dict[str, int] = {}
    for row in impacts:
        severity_counts[row.severity] = severity_counts.get(row.severity, 0) + 1
    session.commit()
    return {
        "context": context.as_dict(),
        "summary": {
            "activeImpacts": len(impacts),
            "openCommands": len(commands),
            "affectedPatients": len({patient for row in impacts for patient in (row.patient_refs or [])}),
            "severityCounts": severity_counts,
        },
        "impacts": [impact_dict(row) for row in impacts],
        "commands": [command_dict(row) for row in commands],
    }


@router.get("/api/v26/convergence")
def convergence_register(
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    resolve_context(session, auth)
    seed_legacy_routes(session)
    rows = session.exec(select(LegacyRouteConvergenceV26).order_by(LegacyRouteConvergenceV26.route_key)).all()
    session.commit()
    return {"routes": [
        {
            "routeKey": row.route_key,
            "method": row.method,
            "legacyPath": row.legacy_path,
            "canonicalCommandType": row.canonical_command_type,
            "canonicalPath": row.canonical_path,
            "status": row.status,
            "retirementState": row.retirement_state,
            "reason": row.reason,
        }
        for row in rows
    ]}


@router.patch("/api/patient-care/episodes/{episode_id}/state")
def converged_update_episode_state(
    episode_id: str,
    payload: EpisodeStatePatch,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    if auth.role not in CLINICAL_ROLES | SENIOR_ROLES:
        raise HTTPException(status_code=403, detail="clinical or senior role required")
    context = resolve_context(session, auth)
    result = v25_update_episode_state(episode_id, payload, session, auth)
    episode = result.get("episode") or {}
    blocker = str(episode.get("blocker") or "none")
    if blocker != "none" or episode.get("status") == "blocked":
        safety = result.get("safetyRecord") or {}
        row, _, _ = record_command(
            session,
            auth,
            context,
            command_type="patient_blocker",
            payload={
                "patientRef": episode.get("patientCaseId"),
                "episodeRef": episode.get("id") or episode_id,
                "summary": payload.note or f"Patient episode blocked by {blocker}",
                "severity": "red",
                "boardSummary": "Patient workflow held pending named review of a recorded blocker.",
                "blocker": blocker,
                "currentLocation": episode.get("currentLocation"),
                "nextAction": episode.get("nextAction"),
            },
            source_route=f"/api/patient-care/episodes/{episode_id}/state",
            source_module="patient-care-v26-convergence",
            source_record_ref=f"{episode_id}:{blocker}",
            legacy_route_key="patient-care-state",
            idempotency_key=f"v26:patient-blocker:{episode_id}:{blocker}",
            outcome_payload=result,
            existing_safety_ref=safety.get("recordRef"),
        )
        session.commit()
        result["canonicalCommand"] = command_dict(row)
        result["operatingContext"] = context.as_dict()
    return result


@router.post("/api/control-plane/handovers")
def converged_create_handover(
    payload: HandoverCreate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    if auth.role not in CLINICAL_ROLES | SENIOR_ROLES:
        raise HTTPException(status_code=403, detail="clinical or senior role required")
    context = resolve_context(session, auth)
    result = v25_create_handover(payload, session, auth)
    handover = result["handover"]
    safety = result.get("safetyRecord") or {}
    row, _, _ = record_command(
        session,
        auth,
        context,
        command_type="handover_request",
        payload={
            "patientCaseId": payload.patientCaseId,
            "referralEpisodeId": payload.referralEpisodeId,
            "summary": payload.summary,
            "clinicalRisks": payload.clinicalRisks,
            "outstandingActions": payload.outstandingActions,
            "toActor": payload.toActor,
            "toRole": payload.toRole,
            "dueAt": payload.dueAt,
            "severity": "red" if payload.clinicalRisks else "amber",
            "boardSummary": "Clinical responsibility remains with the current owner until the named recipient accepts.",
        },
        source_route="/api/control-plane/handovers",
        source_module="control-plane-v26-convergence",
        source_record_ref=handover["handoverRef"],
        legacy_route_key="control-plane-handover-create",
        idempotency_key=f"v26:handover:{handover['handoverRef']}",
        outcome_payload=result,
        existing_safety_ref=safety.get("recordRef"),
    )
    session.commit()
    result["canonicalCommand"] = command_dict(row)
    result["operatingContext"] = context.as_dict()
    return result


@router.patch("/api/control-plane/handovers/{handover_id}/decision")
def converged_decide_handover(
    handover_id: int,
    payload: HandoverDecision,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    context = resolve_context(session, auth)
    result = v25_decide_handover(handover_id, payload, session, auth)
    handover = result["handover"]
    row = update_linked_command(
        session,
        auth,
        context,
        command_type="handover_request",
        source_record_ref=handover["handoverRef"],
        status=str(payload.decision).lower(),
        outcome_payload=result,
        reason=payload.note or f"handover {payload.decision}",
    )
    session.commit()
    result["canonicalCommand"] = command_dict(row)
    result["operatingContext"] = context.as_dict()
    return result


@router.post("/api/control-plane/critical-results")
def converged_create_critical_result(
    payload: CriticalResultCreate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    if auth.role not in CLINICAL_ROLES | SENIOR_ROLES:
        raise HTTPException(status_code=403, detail="clinical or senior role required")
    context = resolve_context(session, auth)
    result = v25_create_critical_result(payload, session, auth)
    critical = result["result"]
    safety = result.get("safetyRecord") or {}
    row, _, _ = record_command(
        session,
        auth,
        context,
        command_type="critical_result_received",
        payload={
            "patientCaseId": payload.patientCaseId,
            "referralEpisodeId": payload.referralEpisodeId,
            "summary": payload.summary,
            "resultType": payload.resultType,
            "severity": payload.severity,
            "assignedTo": payload.assignedTo,
            "assignedRole": payload.assignedRole,
            "dueAt": payload.dueAt,
            "boardSummary": "Critical result remains open until a named clinician records action.",
        },
        source_route="/api/control-plane/critical-results",
        source_module="control-plane-v26-convergence",
        source_record_ref=critical["resultRef"],
        legacy_route_key="control-plane-critical-result-create",
        idempotency_key=f"v26:critical-result:{critical['resultRef']}",
        outcome_payload=result,
        existing_safety_ref=safety.get("recordRef"),
    )
    session.commit()
    result["canonicalCommand"] = command_dict(row)
    result["operatingContext"] = context.as_dict()
    return result


@router.patch("/api/control-plane/critical-results/{result_id}/acknowledge")
def converged_acknowledge_critical_result(
    result_id: int,
    payload: CriticalResultDecision,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    context = resolve_context(session, auth)
    result = v25_acknowledge_critical_result(result_id, payload, session, auth)
    critical = result["result"]
    row = update_linked_command(
        session,
        auth,
        context,
        command_type="critical_result_received",
        source_record_ref=critical["resultRef"],
        status="acknowledged",
        outcome_payload=result,
        reason=payload.note or payload.actionTaken,
    )
    session.commit()
    result["canonicalCommand"] = command_dict(row)
    result["operatingContext"] = context.as_dict()
    return result
