from __future__ import annotations

import asyncio
import json
from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.auth import AuthContext, require_authenticated, require_roles
from app.database import engine, get_session
from app.hospital_ops_models import (
    BoardChangeEvent,
    CanonicalEpisodeState,
    ImportBatch,
    ImportReconciliationItem,
    OperationalBlock,
    OperationalCommand,
    OperationalConflict,
    ScenarioRun,
)
from app.hospital_ops_service import (
    apply_propagated_delay,
    block_dict,
    board_snapshot,
    command_dict,
    commit_import,
    conflict_dict,
    create_block,
    create_episode,
    detect_constraints,
    ensure_default_premises_and_areas,
    episode_dict,
    operational_readiness,
    parse_json,
    patch_block,
    preview_import,
    propagation_preview,
    run_scenario,
    transition_episode,
)

router = APIRouter(prefix="/api/hospital-ops", tags=["hospital-operating-system-v3"])

ALL_ROLES = ("admin", "clinician", "clinical_director", "governance_lead", "hospital_director", "nurse", "ops_manager", "senior_clinician", "supervisor")
OPERATIONAL_WRITE_ROLES = ("clinician", "clinical_director", "hospital_director", "nurse", "ops_manager", "senior_clinician", "supervisor")
SENIOR_ROLES = ("clinical_director", "governance_lead", "hospital_director", "ops_manager", "senior_clinician", "supervisor")


class EpisodeCreate(BaseModel):
    episodeRef: str | None = None
    patientRef: str | None = None
    patientName: str
    premisesRef: str = "default-premises"
    serviceLine: str = "referral"
    urgency: str = "routine"
    gates: dict[str, Any] = Field(default_factory=dict)
    flags: list[Any] = Field(default_factory=list)
    idempotencyKey: str | None = None


class EpisodeTransition(BaseModel):
    expectedVersion: int
    phase: str
    ownerRole: str | None = None
    ownerSubject: str | None = None
    currentAreaRef: str | None = None
    nextAction: str | None = None
    gates: dict[str, Any] | None = None
    reason: str | None = None
    overrideReason: str | None = None
    idempotencyKey: str | None = None


class BlockCreate(BaseModel):
    blockRef: str | None = None
    premisesRef: str = "default-premises"
    episodeRef: str | None = None
    patientRef: str | None = None
    patientName: str | None = None
    procedureRef: str | None = None
    procedureName: str
    blockType: str = "procedure"
    areaRef: str
    startsAt: datetime
    endsAt: datetime
    status: str = "planned"
    riskLevel: str = "amber"
    priority: int = 50
    leadStaffRef: str | None = None
    leadStaffName: str | None = None
    leadStaffRole: str | None = None
    assistantRefs: list[Any] = Field(default_factory=list)
    equipmentRefs: list[Any] = Field(default_factory=list)
    requiredSkills: list[str] = Field(default_factory=list)
    dependencyRefs: list[str] = Field(default_factory=list)
    blockers: list[Any] = Field(default_factory=list)
    gates: dict[str, Any] = Field(default_factory=dict)
    pharmacyRefs: list[Any] = Field(default_factory=list)
    externalRefs: dict[str, Any] = Field(default_factory=dict)
    notes: str | None = None
    reason: str | None = None
    idempotencyKey: str | None = None


class BlockPatch(BaseModel):
    expectedVersion: int
    commandType: str = "PatchOperationalBlock"
    procedureName: str | None = None
    blockType: str | None = None
    areaRef: str | None = None
    startsAt: datetime | None = None
    endsAt: datetime | None = None
    status: str | None = None
    riskLevel: str | None = None
    priority: int | None = None
    leadStaffRef: str | None = None
    leadStaffName: str | None = None
    leadStaffRole: str | None = None
    assistantRefs: list[Any] | None = None
    equipmentRefs: list[Any] | None = None
    requiredSkills: list[str] | None = None
    blockers: list[Any] | None = None
    gates: dict[str, Any] | None = None
    pharmacyRefs: list[Any] | None = None
    notes: str | None = None
    action: str | None = None
    reason: str | None = None
    overrideReason: str | None = None
    idempotencyKey: str | None = None


class DelayPreview(BaseModel):
    minutes: int = Field(ge=-720, le=1440)


class DelayApply(BaseModel):
    minutes: int = Field(ge=-720, le=1440)
    expectedVersions: dict[str, int] = Field(default_factory=dict)
    reason: str | None = None
    overrideReason: str | None = None
    idempotencyKey: str | None = None


class ScenarioPayload(BaseModel):
    scenarioName: str = "referral-hospital-day"
    premisesRef: str = "simulation-premises"
    operationalDate: date | None = None
    seed: int = 42
    caseCount: int = Field(default=40, ge=10, le=100)
    commit: bool = False


class ImportPreviewPayload(BaseModel):
    sourceType: str = "csv"
    sourceName: str = "manual import"
    premisesRef: str = "default-premises"
    content: str
    mapping: dict[str, str] = Field(default_factory=dict)


@router.post("/bootstrap")
def bootstrap(
    premises_ref: str = "default-premises",
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*SENIOR_ROLES)),
) -> dict[str, Any]:
    premises, areas = ensure_default_premises_and_areas(session, premises_ref)
    session.commit()
    return {"premisesRef": premises.premises_ref, "name": premises.name, "areas": len(areas), "actor": auth.actor_name}


@router.get("/board")
def get_board(
    premises_ref: str = "default-premises",
    operational_date: date = Query(default_factory=date.today),
    session: Session = Depends(get_session),
    _: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    result = board_snapshot(session, premises_ref, operational_date)
    session.commit()
    return result


@router.get("/episodes")
def list_episodes(
    premises_ref: str = "default-premises",
    status: str | None = None,
    session: Session = Depends(get_session),
    _: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    query = select(CanonicalEpisodeState).where(CanonicalEpisodeState.premises_ref == premises_ref).order_by(CanonicalEpisodeState.updated_at.desc())
    if status:
        query = query.where(CanonicalEpisodeState.status == status)
    rows = session.exec(query).all()
    return {"episodes": [episode_dict(row) for row in rows], "count": len(rows)}


@router.post("/episodes")
def post_episode(
    payload: EpisodeCreate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*ALL_ROLES)),
) -> dict[str, Any]:
    row, command, created = create_episode(session, payload.model_dump(exclude_none=True), auth)
    session.commit()
    session.refresh(row)
    return {"episode": episode_dict(row), "command": command_dict(command), "created": created}


@router.patch("/episodes/{episode_ref}/transition")
def post_transition(
    episode_ref: str,
    payload: EpisodeTransition,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*OPERATIONAL_WRITE_ROLES)),
) -> dict[str, Any]:
    row, command = transition_episode(session, episode_ref, payload.model_dump(exclude_none=True), auth)
    session.commit()
    session.refresh(row)
    return {"episode": episode_dict(row), "command": command_dict(command)}


@router.post("/blocks")
def post_block(
    payload: BlockCreate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*OPERATIONAL_WRITE_ROLES)),
) -> dict[str, Any]:
    row, command, created = create_block(session, payload.model_dump(exclude_none=True), auth)
    conflicts = detect_constraints(session, row.premises_ref, row.operational_date, persist=True)
    session.commit()
    session.refresh(row)
    return {"block": block_dict(row), "command": command_dict(command), "created": created, "conflicts": conflicts}


@router.patch("/blocks/{block_ref}")
def post_block_patch(
    block_ref: str,
    payload: BlockPatch,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*OPERATIONAL_WRITE_ROLES)),
) -> dict[str, Any]:
    body = payload.model_dump(exclude_none=True)
    row, command = patch_block(session, block_ref, body, auth)
    conflicts = detect_constraints(session, row.premises_ref, row.operational_date, persist=True)
    session.commit()
    session.refresh(row)
    return {"block": block_dict(row), "command": command_dict(command), "conflicts": conflicts}


@router.post("/blocks/{block_ref}/delay-preview")
def post_delay_preview(
    block_ref: str,
    payload: DelayPreview,
    session: Session = Depends(get_session),
    _: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    return propagation_preview(session, block_ref, payload.minutes)


@router.post("/blocks/{block_ref}/delay")
def post_delay(
    block_ref: str,
    payload: DelayApply,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*OPERATIONAL_WRITE_ROLES)),
) -> dict[str, Any]:
    rows, command = apply_propagated_delay(session, block_ref, payload.model_dump(exclude_none=True), auth)
    session.commit()
    return {"blocks": [block_dict(row) for row in rows], "command": command_dict(command)}


@router.get("/conflicts")
def get_conflicts(
    premises_ref: str = "default-premises",
    operational_date: date = Query(default_factory=date.today),
    refresh: bool = True,
    session: Session = Depends(get_session),
    _: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    if refresh:
        detect_constraints(session, premises_ref, operational_date, persist=True)
        session.commit()
    rows = session.exec(select(OperationalConflict).where(OperationalConflict.premises_ref == premises_ref, OperationalConflict.operational_date == operational_date).order_by(OperationalConflict.severity.desc(), OperationalConflict.detected_at.desc())).all()
    return {"conflicts": [conflict_dict(row) for row in rows], "count": len(rows)}


@router.get("/commands")
def get_commands(
    target_ref: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    session: Session = Depends(get_session),
    _: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    query = select(OperationalCommand).order_by(OperationalCommand.created_at.desc())
    if target_ref:
        query = query.where(OperationalCommand.target_ref == target_ref)
    rows = session.exec(query.limit(limit)).all()
    return {"commands": [command_dict(row) for row in rows], "count": len(rows)}


@router.get("/changes")
def get_changes(
    premises_ref: str = "default-premises",
    operational_date: date = Query(default_factory=date.today),
    after_id: int = 0,
    limit: int = Query(default=250, ge=1, le=1000),
    session: Session = Depends(get_session),
    _: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    rows = session.exec(select(BoardChangeEvent).where(BoardChangeEvent.premises_ref == premises_ref, BoardChangeEvent.operational_date == operational_date, BoardChangeEvent.id > after_id).order_by(BoardChangeEvent.id).limit(limit)).all()
    return {
        "changes": [{
            "id": row.id,
            "eventRef": row.event_ref,
            "eventType": row.event_type,
            "entityType": row.entity_type,
            "entityRef": row.entity_ref,
            "entityVersion": row.entity_version,
            "commandRef": row.command_ref,
            "payload": parse_json(row.payload_json, {}),
            "createdAt": row.created_at.isoformat(),
        } for row in rows],
        "lastId": rows[-1].id if rows else after_id,
    }


@router.get("/stream")
def stream_changes(
    request: Request,
    premises_ref: str = "default-premises",
    operational_date: date = Query(default_factory=date.today),
    after_id: int = 0,
    _: AuthContext = Depends(require_authenticated),
) -> StreamingResponse:
    async def events():
        cursor = after_id
        heartbeat = 0
        while not await request.is_disconnected():
            with Session(engine) as session:
                rows = session.exec(select(BoardChangeEvent).where(BoardChangeEvent.premises_ref == premises_ref, BoardChangeEvent.operational_date == operational_date, BoardChangeEvent.id > cursor).order_by(BoardChangeEvent.id).limit(100)).all()
                for row in rows:
                    cursor = int(row.id or cursor)
                    payload = {
                        "id": row.id,
                        "eventRef": row.event_ref,
                        "eventType": row.event_type,
                        "entityType": row.entity_type,
                        "entityRef": row.entity_ref,
                        "entityVersion": row.entity_version,
                        "commandRef": row.command_ref,
                        "payload": parse_json(row.payload_json, {}),
                        "createdAt": row.created_at.isoformat(),
                    }
                    yield f"id: {cursor}\nevent: board-change\ndata: {json.dumps(payload, default=str)}\n\n"
            heartbeat += 1
            if heartbeat % 15 == 0:
                yield f"event: heartbeat\ndata: {json.dumps({'afterId': cursor})}\n\n"
            await asyncio.sleep(1)
    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/simulation/run")
def post_scenario(
    payload: ScenarioPayload,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles(*SENIOR_ROLES)),
) -> dict[str, Any]:
    body = payload.model_dump(exclude_none=True)
    if payload.operationalDate:
        body["operationalDate"] = payload.operationalDate.isoformat()
    run = run_scenario(session, body, auth)
    session.commit()
    return {
        "runRef": run.run_ref,
        "scenarioName": run.scenario_name,
        "premisesRef": run.premises_ref,
        "operationalDate": run.operational_date.isoformat(),
        "status": run.status,
        "committed": run.committed,
        "metrics": parse_json(run.metrics_json, {}),
    }


@router.get("/simulation/runs")
def get_scenarios(
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_session),
    _: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    rows = session.exec(select(ScenarioRun).order_by(ScenarioRun.created_at.desc()).limit(limit)).all()
    return {"runs": [{"runRef": row.run_ref, "scenarioName": row.scenario_name, "premisesRef": row.premises_ref, "operationalDate": row.operational_date.isoformat(), "status": row.status, "committed": row.committed, "metrics": parse_json(row.metrics_json, {}), "createdAt": row.created_at.isoformat()} for row in rows]}


@router.post("/imports/preview")
def post_import_preview(
    payload: ImportPreviewPayload,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles("admin", *SENIOR_ROLES)),
) -> dict[str, Any]:
    batch = preview_import(session, payload.model_dump(), auth)
    session.commit()
    return {"batchRef": batch.batch_ref, "status": batch.status, "rowCount": batch.row_count, "acceptedCount": batch.accepted_count, "rejectedCount": batch.rejected_count, "summary": parse_json(batch.summary_json, {})}


@router.post("/imports/{batch_ref}/commit")
def post_import_commit(
    batch_ref: str,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_roles("admin", *SENIOR_ROLES)),
) -> dict[str, Any]:
    batch, rows = commit_import(session, batch_ref, auth)
    dates = sorted({row.operational_date for row in rows})
    for operational_date in dates:
        detect_constraints(session, batch.premises_ref, operational_date, persist=True)
    session.commit()
    return {"batchRef": batch.batch_ref, "status": batch.status, "createdBlocks": [block_dict(row) for row in rows], "createdCount": len(rows)}


@router.get("/imports/{batch_ref}")
def get_import(
    batch_ref: str,
    session: Session = Depends(get_session),
    _: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    batch = session.exec(select(ImportBatch).where(ImportBatch.batch_ref == batch_ref)).first()
    if not batch:
        return {"batch": None, "items": []}
    items = session.exec(select(ImportReconciliationItem).where(ImportReconciliationItem.batch_ref == batch_ref).order_by(ImportReconciliationItem.row_number)).all()
    return {
        "batch": {"batchRef": batch.batch_ref, "sourceType": batch.source_type, "sourceName": batch.source_name, "status": batch.status, "rowCount": batch.row_count, "acceptedCount": batch.accepted_count, "rejectedCount": batch.rejected_count, "summary": parse_json(batch.summary_json, {}), "createdAt": batch.created_at.isoformat()},
        "items": [{"itemRef": item.item_ref, "rowNumber": item.row_number, "status": item.status, "issueType": item.issue_type, "detail": item.detail, "sourceRecord": parse_json(item.source_record_json, {}), "suggestedMatch": parse_json(item.suggested_match_json, {})} for item in items],
    }


@router.get("/readiness")
def get_readiness(
    session: Session = Depends(get_session),
    _: AuthContext = Depends(require_roles(*SENIOR_ROLES)),
) -> dict[str, Any]:
    return operational_readiness(session)
