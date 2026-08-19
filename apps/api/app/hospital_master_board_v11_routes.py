from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.auth import AuthContext, require_authenticated, require_roles
from app.clinical_execution_models import ClinicalObservation, DiagnosticWorkItem, TreatmentTask
from app.control_plane_models import AccountableHandover, CriticalResultAcknowledgement
from app.database import get_session
from app.evidence_service import create_evidence_event
from app.operating_context_v26_service import OperatingContext, resolve_context
from app.hospital_ops_models import OperationalArea, OperationalBlock, OperationalCommand
from app.hospital_ops_service import (
    block_dict,
    board_snapshot,
    create_block,
    detect_constraints,
    json_text,
    normalise_dt,
    parse_json,
    patch_block,
    patch_episode_operational,
)

router = APIRouter(prefix="/api/v11/master-board", tags=["hospital-master-board-v11"])
COORDINATION_WRITE_ROLES = (
    "admin",
    "clinician",
    "clinical_director",
    "hospital_director",
    "nurse",
    "ops_manager",
    "senior_clinician",
    "supervisor",
)
CRITICAL_RESULT_ROLES = ("clinical_director", "hospital_director", "senior_clinician", "clinician")
SENIOR_COORDINATION_ROLES = {"clinical_director", "hospital_director", "ops_manager", "senior_clinician", "supervisor"}

WRITE_ROLES = (
    "clinical_director",
    "hospital_director",
    "ops_manager",
    "senior_clinician",
    "supervisor",
)


def authorised_context(
    session: Session,
    auth: AuthContext,
    requested_premises_ref: str | None = None,
) -> OperatingContext:
    context = resolve_context(session, auth)
    if requested_premises_ref not in {None, "", "default-premises", context.premises_ref}:
        raise HTTPException(status_code=403, detail={
            "code": "site_not_authorised",
            "activePremisesRef": context.premises_ref,
        })
    return context


class EmergencyPreviewPayload(BaseModel):
    premisesRef: str = "default-premises"
    operationalDate: date
    episodeRef: str | None = None
    patientRef: str | None = None
    patientName: str
    procedureName: str
    areaTypes: list[str] = Field(default_factory=lambda: ["theatre"])
    earliestStart: datetime
    latestStart: datetime
    durationMinutes: int = Field(default=90, ge=15, le=720)
    turnoverMinutes: int = Field(default=20, ge=0, le=180)
    requiredSkills: list[str] = Field(default_factory=list)
    equipmentRefs: list[str] = Field(default_factory=list)
    leadStaffRef: str | None = None
    leadStaffName: str | None = None
    leadStaffRole: str | None = None
    priority: int = Field(default=100, ge=1, le=1000)
    maxDisplacedBlocks: int = Field(default=6, ge=0, le=20)


class EmergencyApplyPayload(EmergencyPreviewPayload):
    areaRef: str
    startsAt: datetime
    optionRef: str
    expectedVersions: dict[str, int] = Field(default_factory=dict)
    reason: str
    idempotencyKey: str


class EpisodeOperationalPatch(BaseModel):
    premisesRef: str = "default-premises"
    expectedVersion: int
    ownerRole: str | None = None
    ownerSubject: str | None = None
    currentAreaRef: str | None = None
    nextAction: str | None = None
    reason: str
    idempotencyKey: str


class HandoverCreateV11(BaseModel):
    premisesRef: str = "default-premises"
    toActor: str | None = None
    toRole: str
    summary: str
    clinicalRisks: list[str] = Field(default_factory=list)
    outstandingActions: list[dict[str, Any] | str] = Field(default_factory=list)
    escalationThreshold: str | None = None
    dueAt: datetime | None = None
    idempotencyKey: str


class HandoverDecisionV11(BaseModel):
    premisesRef: str = "default-premises"
    decision: str
    note: str | None = None


class CriticalResultDecisionV11(BaseModel):
    premisesRef: str = "default-premises"
    actionTaken: str
    note: str | None = None


def _round_up_quarter(value: datetime) -> datetime:
    value = normalise_dt(value)
    minute = ((value.minute + 14) // 15) * 15
    if minute == 60:
        return value.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    return value.replace(minute=minute, second=0, microsecond=0)


def _overlaps(start_a: datetime, end_a: datetime, start_b: datetime, end_b: datetime) -> bool:
    return normalise_dt(start_a) < normalise_dt(end_b) and normalise_dt(start_b) < normalise_dt(end_a)


def _option_ref(payload: EmergencyPreviewPayload, area_ref: str, starts_at: datetime, affected: list[dict[str, Any]]) -> str:
    canonical = {
        "premisesRef": payload.premisesRef,
        "operationalDate": payload.operationalDate.isoformat(),
        "episodeRef": payload.episodeRef,
        "patientRef": payload.patientRef,
        "procedureName": payload.procedureName,
        "areaRef": area_ref,
        "startsAt": normalise_dt(starts_at).isoformat(),
        "durationMinutes": payload.durationMinutes,
        "priority": payload.priority,
        "affected": affected,
    }
    return "emergency-option-" + hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()[:24]


def _candidate(
    payload: EmergencyPreviewPayload,
    area: OperationalArea,
    starts_at: datetime,
    blocks: list[OperationalBlock],
) -> dict[str, Any] | None:
    starts_at = normalise_dt(starts_at)
    emergency_end = starts_at + timedelta(minutes=payload.durationMinutes)
    protected_end = emergency_end + timedelta(minutes=max(payload.turnoverMinutes, area.turnover_minutes))

    area_blocks = sorted(
        [row for row in blocks if row.area_ref == area.area_ref],
        key=lambda row: normalise_dt(row.starts_at),
    )
    direct = [row for row in area_blocks if _overlaps(starts_at, protected_end, row.starts_at, row.ends_at)]
    if any(row.status in {"started", "in_progress", "completed"} for row in direct):
        return None
    if any(row.priority >= payload.priority for row in direct):
        return None

    affected: list[dict[str, Any]] = []
    cursor = protected_end
    queue = list(direct)
    visited: set[str] = set()
    while queue:
        row = queue.pop(0)
        if row.block_ref in visited:
            continue
        visited.add(row.block_ref)
        duration = normalise_dt(row.ends_at) - normalise_dt(row.starts_at)
        proposed_start = max(normalise_dt(row.starts_at), cursor)
        proposed_end = proposed_start + duration
        affected.append({
            "blockRef": row.block_ref,
            "patientName": row.patient_name,
            "procedureName": row.procedure_name,
            "currentStartsAt": normalise_dt(row.starts_at).isoformat(),
            "currentEndsAt": normalise_dt(row.ends_at).isoformat(),
            "proposedStartsAt": proposed_start.isoformat(),
            "proposedEndsAt": proposed_end.isoformat(),
            "expectedVersion": row.version,
            "priority": row.priority,
        })
        cursor = proposed_end + timedelta(minutes=area.turnover_minutes)
        for later in area_blocks:
            if later.block_ref in visited:
                continue
            if _overlaps(proposed_start, cursor, later.starts_at, later.ends_at):
                if later.status in {"started", "in_progress", "completed"} or later.priority >= payload.priority:
                    return None
                queue.append(later)
        if len(affected) > payload.maxDisplacedBlocks:
            return None

    requested_equipment = set(payload.equipmentRefs)
    if requested_equipment:
        for row in blocks:
            if row.area_ref == area.area_ref and row.block_ref in visited:
                continue
            if not _overlaps(starts_at, emergency_end, row.starts_at, row.ends_at):
                continue
            if requested_equipment & set(parse_json(row.equipment_refs_json, [])):
                return None

    displacement_minutes = sum(
        max(
            0,
            int((datetime.fromisoformat(item["proposedStartsAt"]) - datetime.fromisoformat(item["currentStartsAt"])).total_seconds() // 60),
        )
        for item in affected
    )
    start_delay = max(0, int((starts_at - normalise_dt(payload.earliestStart)).total_seconds() // 60))
    score = (len(affected) * 1000) + displacement_minutes + start_delay
    warnings: list[str] = []
    if not payload.leadStaffRef:
        warnings.append("Emergency lead clinician is not assigned")
    area_skills = set(parse_json(area.required_skills_json, []))
    missing_area_skills = sorted(set(payload.requiredSkills) - area_skills)
    if missing_area_skills:
        warnings.append("Area configuration does not declare skills: " + ", ".join(missing_area_skills))

    return {
        "optionRef": _option_ref(payload, area.area_ref, starts_at, affected),
        "areaRef": area.area_ref,
        "areaName": area.name,
        "startsAt": starts_at.isoformat(),
        "endsAt": emergency_end.isoformat(),
        "affected": affected,
        "displacedCount": len(affected),
        "totalDisplacementMinutes": displacement_minutes,
        "warnings": warnings,
        "score": score,
    }


def emergency_options(session: Session, payload: EmergencyPreviewPayload) -> list[dict[str, Any]]:
    earliest = _round_up_quarter(payload.earliestStart)
    latest = normalise_dt(payload.latestStart)
    if latest < earliest:
        raise HTTPException(status_code=422, detail="latestStart must be after earliestStart")
    areas = session.exec(
        select(OperationalArea).where(
            OperationalArea.premises_ref == payload.premisesRef,
            OperationalArea.active == True,  # noqa: E712
        )
    ).all()
    areas = [area for area in areas if area.area_type in set(payload.areaTypes)]
    if not areas:
        raise HTTPException(status_code=409, detail="no active operational areas match the emergency request")
    blocks = session.exec(
        select(OperationalBlock).where(
            OperationalBlock.premises_ref == payload.premisesRef,
            OperationalBlock.operational_date == payload.operationalDate,
            OperationalBlock.status.notin_(["cancelled", "completed"]),
        )
    ).all()
    options: list[dict[str, Any]] = []
    slot = earliest
    while slot <= latest:
        for area in areas:
            candidate = _candidate(payload, area, slot, blocks)
            if candidate:
                options.append(candidate)
        slot += timedelta(minutes=15)
    return sorted(options, key=lambda item: (item["score"], item["startsAt"], item["areaName"]))[:20]


@router.get("/day")
def get_day(
    premises_ref: str = "default-premises",
    operational_date: date = Query(default_factory=date.today),
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    context = authorised_context(session, auth, premises_ref)
    board = board_snapshot(session, context.premises_ref, operational_date)
    now = datetime.now(timezone.utc)
    horizon = now + timedelta(minutes=90)
    live_blocks = [
        block for block in board["blocks"]
        if datetime.fromisoformat(block["endsAt"]) >= now
        and datetime.fromisoformat(block["startsAt"]) <= horizon
    ]
    board["liveWindow"] = {
        "from": now.isoformat(),
        "to": horizon.isoformat(),
        "blocks": sorted(live_blocks, key=lambda item: item["startsAt"]),
    }
    board["boardVersion"] = "v11"
    board["operatingContext"] = context.as_dict()
    board["requestedBy"] = auth.subject
    session.commit()
    return board


def _episode_for_context(session: Session, episode_ref: str, context: OperatingContext) -> CanonicalEpisodeState:
    episode = session.exec(select(CanonicalEpisodeState).where(CanonicalEpisodeState.episode_ref == episode_ref)).first()
    if not episode:
        raise HTTPException(status_code=404, detail="episode not found")
    if episode.premises_ref != context.premises_ref:
        raise HTTPException(status_code=403, detail={"code": "site_not_authorised", "activePremisesRef": context.premises_ref})
    return episode


def _handover_dict(row: AccountableHandover) -> dict[str, Any]:
    return {
        "id": row.id,
        "handoverRef": row.handover_ref,
        "episodeRef": row.referral_episode_id,
        "fromActor": row.from_actor,
        "fromRole": row.from_role,
        "toActor": row.to_actor,
        "toRole": row.to_role,
        "status": row.status,
        "summary": row.summary,
        "clinicalRisks": parse_json(row.clinical_risks_json, []),
        "outstandingActions": parse_json(row.outstanding_actions_json, []),
        "escalationThreshold": row.escalation_threshold,
        "dueAt": row.due_at.isoformat() if row.due_at else None,
        "acceptedBy": row.accepted_by,
        "acceptedByRole": row.accepted_by_role,
        "acceptedAt": row.accepted_at.isoformat() if row.accepted_at else None,
        "decisionNote": row.decision_note,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
    }


def _critical_result_dict(row: CriticalResultAcknowledgement) -> dict[str, Any]:
    return {
        "id": row.id,
        "resultRef": row.result_ref,
        "episodeRef": row.referral_episode_id,
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
        "createdAt": row.created_at.isoformat() if row.created_at else None,
    }


@router.get("/coordination")
def get_coordination(
    premises_ref: str = "default-premises",
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    context = authorised_context(session, auth, premises_ref)
    episode_refs = [
        row.episode_ref
        for row in session.exec(
            select(CanonicalEpisodeState).where(
                CanonicalEpisodeState.premises_ref == context.premises_ref,
                CanonicalEpisodeState.status == "active",
            )
        ).all()
    ]
    if not episode_refs:
        return {
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "handovers": [],
            "criticalResults": [],
            "diagnostics": [],
            "tasks": [],
            "observations": [],
            "summary": {"pendingHandovers": 0, "unacknowledgedCriticalResults": 0, "overdueTasks": 0, "redObservations": 0},
        }

    handovers = session.exec(
        select(AccountableHandover)
        .where(AccountableHandover.referral_episode_id.in_(episode_refs))
        .order_by(AccountableHandover.created_at.desc())
    ).all()
    results = session.exec(
        select(CriticalResultAcknowledgement)
        .where(CriticalResultAcknowledgement.referral_episode_id.in_(episode_refs))
        .order_by(CriticalResultAcknowledgement.created_at.desc())
    ).all()
    diagnostics = session.exec(
        select(DiagnosticWorkItem)
        .where(DiagnosticWorkItem.episode_ref.in_(episode_refs))
        .order_by(DiagnosticWorkItem.requested_test)
    ).all()
    tasks = session.exec(
        select(TreatmentTask)
        .where(TreatmentTask.episode_ref.in_(episode_refs))
        .order_by(TreatmentTask.due_at)
    ).all()
    observations = session.exec(
        select(ClinicalObservation)
        .where(ClinicalObservation.episode_ref.in_(episode_refs))
        .order_by(ClinicalObservation.recorded_at.desc())
    ).all()
    now = datetime.now(timezone.utc)
    task_rows = [{
        "taskRef": row.task_ref,
        "episodeRef": row.episode_ref,
        "title": row.title,
        "status": row.status,
        "dueAt": row.due_at.isoformat(),
        "priority": row.priority,
        "assignedRole": row.assigned_role,
        "version": row.version,
    } for row in tasks]
    observation_rows = [{
        "observationRef": row.observation_ref,
        "episodeRef": row.episode_ref,
        "type": row.observation_type,
        "concernLevel": row.concern_level,
        "escalationStatus": row.escalation_status,
        "recordedAt": row.recorded_at.isoformat(),
    } for row in observations]
    diagnostic_rows = [{
        "workRef": row.work_ref,
        "episodeRef": row.episode_ref,
        "modality": row.modality,
        "requestedTest": row.requested_test,
        "urgency": row.urgency,
        "status": row.status,
        "assignedService": row.assigned_service,
        "acquiredAt": row.acquired_at.isoformat() if row.acquired_at else None,
        "reportedAt": row.reported_at.isoformat() if row.reported_at else None,
        "reportSummary": row.report_summary,
        "criticalResult": row.critical_result,
        "version": row.version,
    } for row in diagnostics]
    return {
        "generatedAt": now.isoformat(),
        "handovers": [_handover_dict(row) for row in handovers],
        "criticalResults": [_critical_result_dict(row) for row in results],
        "diagnostics": diagnostic_rows,
        "tasks": task_rows,
        "observations": observation_rows,
        "summary": {
            "pendingHandovers": len([row for row in handovers if row.status == "pending"]),
            "unacknowledgedCriticalResults": len([row for row in results if row.status == "awaiting_acknowledgement"]),
            "overdueTasks": len([row for row in tasks if row.status != "completed" and normalise_dt(row.due_at) < now]),
            "redObservations": len([row for row in observations if row.concern_level == "red" and row.escalation_status == "pending"]),
        },
    }


@router.patch("/episodes/{episode_ref}/operational")
def update_episode_operational(
    episode_ref: str,
    payload: EpisodeOperationalPatch,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*COORDINATION_WRITE_ROLES)),
) -> dict[str, Any]:
    context = authorised_context(session, auth, payload.premisesRef)
    _episode_for_context(session, episode_ref, context)
    row, command = patch_episode_operational(session, episode_ref, payload.model_dump(exclude_none=True), auth)
    session.commit()
    session.refresh(row)
    return {"episode": episode_dict(row), "commandRef": command.command_ref}


@router.post("/episodes/{episode_ref}/handovers")
def create_episode_handover(
    episode_ref: str,
    payload: HandoverCreateV11,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*COORDINATION_WRITE_ROLES)),
) -> dict[str, Any]:
    context = authorised_context(session, auth, payload.premisesRef)
    episode = _episode_for_context(session, episode_ref, context)
    handover_ref = "handover-v11-" + hashlib.sha256(payload.idempotencyKey.encode("utf-8")).hexdigest()[:24]
    existing = session.exec(select(AccountableHandover).where(AccountableHandover.handover_ref == handover_ref)).first()
    if existing:
        if existing.referral_episode_id != episode_ref:
            raise HTTPException(status_code=409, detail="idempotency key belongs to another handover")
        return {"handover": _handover_dict(existing), "created": False}

    row = AccountableHandover(
        handover_ref=handover_ref,
        patient_case_id=episode.patient_ref,
        referral_episode_id=episode_ref,
        from_actor=auth.actor_name,
        from_role=auth.role,
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
        patient_case_id=episode.patient_ref,
        referral_episode_id=episode_ref,
        actor_id=auth.subject,
        actor_name=auth.actor_name,
        actor_role=auth.role,
        actor_auth_source=auth.auth_source,
        new_state=_handover_dict(row),
        reason="responsibility transfer requires explicit acceptance",
        evidence_links=[{"type": "handover", "id": handover_ref}],
        compliance_domain="clinical_governance",
        risk_level="red" if payload.clinicalRisks else "amber",
        source_module="hospital-master-board-v11",
        source_record_ref=handover_ref,
        entity_type="handover",
        entity_id=handover_ref,
        idempotency_key=f"v11:{payload.idempotencyKey}",
    )
    row.evidence_event_ref = event.event_ref
    session.add(row)
    session.commit()
    session.refresh(row)
    return {"handover": _handover_dict(row), "created": True}


@router.patch("/handovers/{handover_id}/decision")
def decide_episode_handover(
    handover_id: int,
    payload: HandoverDecisionV11,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*COORDINATION_WRITE_ROLES)),
) -> dict[str, Any]:
    context = authorised_context(session, auth, payload.premisesRef)
    query = select(AccountableHandover).where(AccountableHandover.id == handover_id)
    if session.get_bind().dialect.name == "postgresql":
        query = query.with_for_update()
    row = session.exec(query).first()
    if not row:
        raise HTTPException(status_code=404, detail="handover not found")
    _episode_for_context(session, row.referral_episode_id, context)
    if row.status != "pending":
        raise HTTPException(status_code=409, detail="handover already decided")
    if auth.role != row.to_role and auth.role not in SENIOR_COORDINATION_ROLES:
        raise HTTPException(status_code=403, detail="handover must be decided by the receiving role or a senior coordinator")
    decision = payload.decision.lower().strip()
    if decision not in {"accepted", "rejected", "escalated"}:
        raise HTTPException(status_code=422, detail="decision must be accepted, rejected or escalated")

    previous = _handover_dict(row)
    row.status = decision
    row.accepted_by = auth.actor_name
    row.accepted_by_role = auth.role
    row.accepted_at = datetime.now(timezone.utc)
    row.decision_note = payload.note
    event, _ = create_evidence_event(
        session,
        event_type="handover_decision",
        action=f"handover {decision}",
        patient_case_id=row.patient_case_id,
        referral_episode_id=row.referral_episode_id,
        actor_id=auth.subject,
        actor_name=auth.actor_name,
        actor_role=auth.role,
        actor_auth_source=auth.auth_source,
        previous_state=previous,
        new_state=_handover_dict(row),
        reason="named recipient decision",
        justification=payload.note,
        evidence_links=[{"type": "handover", "id": row.handover_ref}],
        compliance_domain="clinical_governance",
        risk_level="green" if decision == "accepted" else "red",
        source_module="hospital-master-board-v11",
        source_record_ref=row.handover_ref,
        causation_event_ref=row.evidence_event_ref,
        entity_type="handover",
        entity_id=row.handover_ref,
    )
    row.evidence_event_ref = event.event_ref
    session.add(row)
    session.commit()
    session.refresh(row)
    return {"handover": _handover_dict(row)}


@router.patch("/critical-results/{result_id}/acknowledge")
def acknowledge_critical_result(
    result_id: int,
    payload: CriticalResultDecisionV11,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*CRITICAL_RESULT_ROLES)),
) -> dict[str, Any]:
    context = authorised_context(session, auth, payload.premisesRef)
    query = select(CriticalResultAcknowledgement).where(CriticalResultAcknowledgement.id == result_id)
    if session.get_bind().dialect.name == "postgresql":
        query = query.with_for_update()
    row = session.exec(query).first()
    if not row:
        raise HTTPException(status_code=404, detail="critical result not found")
    _episode_for_context(session, row.referral_episode_id, context)
    if row.status != "awaiting_acknowledgement":
        raise HTTPException(status_code=409, detail="critical result already acknowledged")
    action_taken = payload.actionTaken.strip()
    if not action_taken:
        raise HTTPException(status_code=422, detail="actionTaken is required")

    previous = _critical_result_dict(row)
    row.status = "acknowledged"
    row.acknowledged_by = auth.actor_name
    row.acknowledged_at = datetime.now(timezone.utc)
    row.action_taken = action_taken
    event, _ = create_evidence_event(
        session,
        event_type="critical_result_acknowledged",
        action="critical result acknowledged and action recorded",
        patient_case_id=row.patient_case_id,
        referral_episode_id=row.referral_episode_id,
        actor_id=auth.subject,
        actor_name=auth.actor_name,
        actor_role=auth.role,
        actor_auth_source=auth.auth_source,
        previous_state=previous,
        new_state=_critical_result_dict(row),
        reason=row.summary,
        justification=payload.note or action_taken,
        compliance_domain="diagnostics",
        risk_level="green",
        source_module="hospital-master-board-v11",
        source_record_ref=row.result_ref,
        causation_event_ref=row.evidence_event_ref,
        entity_type="critical_result",
        entity_id=row.result_ref,
    )
    row.evidence_event_ref = event.event_ref
    session.add(row)
    session.commit()
    session.refresh(row)
    return {"result": _critical_result_dict(row)}


@router.post("/emergency/preview")
def preview_emergency(
    payload: EmergencyPreviewPayload,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*WRITE_ROLES)),
) -> dict[str, Any]:
    context = authorised_context(session, auth, payload.premisesRef)
    payload = payload.model_copy(update={"premisesRef": context.premises_ref})
    options = emergency_options(session, payload)
    return {
        "request": payload.model_dump(mode="json"),
        "options": options,
        "canInsert": bool(options),
        "explanation": "Options are ranked by displaced-case count, total displacement and delay from the earliest requested start.",
    }


@router.post("/emergency/apply")
def apply_emergency(
    payload: EmergencyApplyPayload,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*WRITE_ROLES)),
) -> dict[str, Any]:
    context = authorised_context(session, auth, payload.premisesRef)
    payload = payload.model_copy(update={"premisesRef": context.premises_ref})
    existing = session.exec(
        select(OperationalCommand).where(OperationalCommand.idempotency_key == payload.idempotencyKey)
    ).first()
    if existing:
        if existing.command_type != "CreateOperationalBlock":
            raise HTTPException(status_code=409, detail="idempotency key belongs to another command")
        return json.loads(existing.result_json or "{}")

    preview_payload = EmergencyPreviewPayload(**payload.model_dump(exclude={
        "areaRef", "startsAt", "optionRef", "expectedVersions", "reason", "idempotencyKey"
    }))
    options = emergency_options(session, preview_payload)
    selected = next(
        (
            item for item in options
            if item["optionRef"] == payload.optionRef
            and item["areaRef"] == payload.areaRef
            and normalise_dt(datetime.fromisoformat(item["startsAt"])) == normalise_dt(payload.startsAt)
        ),
        None,
    )
    if not selected:
        raise HTTPException(status_code=409, detail="emergency option is stale or no longer safe")

    affected_refs = sorted(item["blockRef"] for item in selected["affected"])
    if affected_refs:
        lock_query = select(OperationalBlock).where(OperationalBlock.block_ref.in_(affected_refs)).order_by(OperationalBlock.block_ref)
        if session.get_bind().dialect.name == "postgresql":
            lock_query = lock_query.with_for_update()
        locked_rows = {row.block_ref: row for row in session.exec(lock_query).all()}
        for item in selected["affected"]:
            row = locked_rows.get(item["blockRef"])
            expected = payload.expectedVersions.get(item["blockRef"])
            if not row or expected is None or row.version != expected or expected != item["expectedVersion"]:
                raise HTTPException(status_code=409, detail={
                    "message": "displacement plan is stale",
                    "blockRef": item["blockRef"],
                    "expectedVersion": item["expectedVersion"],
                    "currentVersion": row.version if row else None,
                })

    emergency, create_command, created = create_block(
        session,
        {
            "premisesRef": payload.premisesRef,
            "episodeRef": payload.episodeRef,
            "patientRef": payload.patientRef,
            "patientName": payload.patientName,
            "procedureName": payload.procedureName,
            "blockType": "emergency",
            "areaRef": payload.areaRef,
            "startsAt": payload.startsAt,
            "endsAt": normalise_dt(payload.startsAt) + timedelta(minutes=payload.durationMinutes),
            "status": "planned",
            "riskLevel": "red",
            "priority": payload.priority,
            "leadStaffRef": payload.leadStaffRef,
            "leadStaffName": payload.leadStaffName,
            "leadStaffRole": payload.leadStaffRole,
            "equipmentRefs": payload.equipmentRefs,
            "requiredSkills": payload.requiredSkills,
            "notes": "Governed emergency insertion v11",
            "reason": payload.reason,
            "idempotencyKey": payload.idempotencyKey,
        },
        auth,
    )

    displaced: list[dict[str, Any]] = []
    for item in selected["affected"]:
        row, command = patch_block(
            session,
            item["blockRef"],
            {
                "expectedVersion": item["expectedVersion"],
                "commandType": "EmergencyDisplacementV11",
                "startsAt": item["proposedStartsAt"],
                "endsAt": item["proposedEndsAt"],
                "riskLevel": "amber",
                "action": "displaced by governed emergency insertion",
                "reason": payload.reason,
                "idempotencyKey": f"{payload.idempotencyKey}:displace:{item['blockRef']}",
            },
            auth,
        )
        displaced.append({"block": block_dict(row), "commandRef": command.command_ref})

    conflicts = detect_constraints(session, payload.premisesRef, payload.operationalDate, persist=True)
    session.flush()
    result = {
        "created": created,
        "emergencyBlock": block_dict(emergency),
        "createCommandRef": create_command.command_ref,
        "displaced": displaced,
        "conflicts": conflicts,
        "option": selected,
    }
    create_command.result_json = json.dumps(result, default=str, sort_keys=True)
    session.add(create_command)
    session.commit()
    session.refresh(emergency)
    result["emergencyBlock"] = block_dict(emergency)
    return result
