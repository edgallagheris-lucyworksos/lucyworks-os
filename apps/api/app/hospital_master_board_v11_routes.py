from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.auth import AuthContext, require_authenticated, require_roles
from app.database import get_session
from app.hospital_ops_models import OperationalArea, OperationalBlock, OperationalCommand
from app.hospital_ops_service import (
    block_dict,
    board_snapshot,
    create_block,
    detect_constraints,
    normalise_dt,
    parse_json,
    patch_block,
)

router = APIRouter(prefix="/api/v11/master-board", tags=["hospital-master-board-v11"])
WRITE_ROLES = (
    "clinical_director",
    "hospital_director",
    "ops_manager",
    "senior_clinician",
    "supervisor",
)


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
    board = board_snapshot(session, premises_ref, operational_date)
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
    board["requestedBy"] = auth.subject
    session.commit()
    return board


@router.post("/emergency/preview")
def preview_emergency(
    payload: EmergencyPreviewPayload,
    session: Session = Depends(get_session),
    _: AuthContext = Depends(require_roles(*WRITE_ROLES)),
) -> dict[str, Any]:
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
