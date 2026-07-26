from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.auth import AuthContext, require_authenticated
from app.database import get_session
from app.hospital_ops_models import CanonicalEpisodeState, OperationalBlock, OperationalConflict
from app.hospital_ops_service import parse_json
from app.models import WorkItem

router = APIRouter(prefix="/api/v16/care-brief", tags=["care-brief-v16"])

_COMPLETE = {True, "approved", "accepted", "authorised", "ready", "complete", "completed", "not_required", "emergency_authority"}
_GATE_LABELS = {
    "consent": "Consent evidence incomplete",
    "estimate": "Estimate or financial authority incomplete",
    "insurance": "Insurance decision incomplete",
    "pharmacy": "Medication readiness incomplete",
    "records": "Clinical record incomplete",
    "handover": "Handover acknowledgement incomplete",
    "results": "Results review incomplete",
    "discharge": "Discharge evidence incomplete",
    "owner_communication": "Owner communication incomplete",
    "referring_vet_report": "Referring-vet report incomplete",
}


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _iso(value: datetime | None) -> str | None:
    normalised = _utc(value)
    return normalised.isoformat() if normalised else None


def _gate_gaps(gates: dict[str, Any]) -> list[str]:
    gaps: list[str] = []
    for key, label in _GATE_LABELS.items():
        if key in gates and gates[key] not in _COMPLETE:
            gaps.append(label)
    return gaps


def _task(row: WorkItem, now: datetime) -> dict[str, Any]:
    due = _utc(row.due_at)
    return {
        "id": row.id,
        "title": row.title,
        "description": row.description,
        "urgency": row.urgency,
        "status": row.status,
        "ownerRole": row.owner_role,
        "area": row.room_name or row.section_name,
        "dueAt": _iso(row.due_at),
        "overdue": bool(due and due < now and row.status != "done"),
    }


def _block(row: OperationalBlock) -> dict[str, Any]:
    return {
        "blockRef": row.block_ref,
        "procedureName": row.procedure_name,
        "areaRef": row.area_ref,
        "areaName": row.area_name,
        "startsAt": _iso(row.starts_at),
        "endsAt": _iso(row.ends_at),
        "status": row.status,
        "riskLevel": row.risk_level,
        "leadStaffName": row.lead_staff_name,
        "leadStaffRole": row.lead_staff_role,
        "blockers": parse_json(row.blockers_json, []) or [],
        "gates": parse_json(row.gates_json, {}) or {},
    }


@router.get("/{episode_ref}")
def care_brief(
    episode_ref: str,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    episode = session.exec(select(CanonicalEpisodeState).where(CanonicalEpisodeState.episode_ref == episode_ref)).first()
    if not episode:
        raise HTTPException(status_code=404, detail="canonical episode not found")

    now = datetime.now(timezone.utc)
    block_rows = session.exec(
        select(OperationalBlock).where(
            OperationalBlock.episode_ref == episode_ref,
            OperationalBlock.status != "cancelled",
        ).order_by(OperationalBlock.starts_at)
    ).all()
    task_rows = session.exec(
        select(WorkItem).where(
            WorkItem.linked_episode_ref == episode_ref,
            WorkItem.status != "done",
        ).order_by(WorkItem.due_at, WorkItem.created_at)
    ).all()

    blocks = [_block(row) for row in block_rows]
    tasks = [_task(row, now) for row in task_rows]
    block_refs = {row.block_ref for row in block_rows}
    conflict_rows = session.exec(
        select(OperationalConflict).where(
            OperationalConflict.premises_ref == episode.premises_ref,
            OperationalConflict.status == "open",
        ).order_by(OperationalConflict.detected_at)
    ).all()
    conflicts: list[dict[str, Any]] = []
    for row in conflict_rows:
        related = [str(value) for value in (parse_json(row.related_refs_json, []) or [])]
        if row.primary_block_ref not in block_refs and not block_refs.intersection(related):
            continue
        conflicts.append({
            "conflictRef": row.conflict_ref,
            "severity": row.severity,
            "type": row.conflict_type,
            "explanation": row.explanation,
        })

    current = next((row for row in block_rows if row.status in {"started", "in_progress"}), None)
    if current is None:
        current = next((row for row in block_rows if (_utc(row.starts_at) or now) <= now < (_utc(row.ends_at) or now)), None)
    next_block = next((row for row in block_rows if (_utc(row.starts_at) or now) > now), None)
    relevant = current or next_block

    gates = parse_json(episode.gates_json, {}) or {}
    flags = [str(value) for value in (parse_json(episode.flags_json, []) or [])]
    gate_gaps = _gate_gaps(gates)
    block_gaps = [str(item) for block in blocks for item in block["blockers"]]
    critical_tasks = [row for row in tasks if row["urgency"] == "red" or row["overdue"] or row["status"] == "blocked"]
    red_conflicts = [row for row in conflicts if row["severity"].lower() == "red"]
    attention = list(dict.fromkeys([*gate_gaps, *block_gaps, *flags, *[row["title"] for row in critical_tasks], *[row["explanation"] for row in conflicts]]))
    deadline_tasks = [row for row in tasks if row["dueAt"]]
    next_deadline = min(deadline_tasks, key=lambda row: row["dueAt"] or "") if deadline_tasks else None

    return {
        "briefVersion": "v16",
        "generatedAt": now.isoformat(),
        "episodeRef": episode.episode_ref,
        "patientRef": episode.patient_ref,
        "patientName": episode.patient_name,
        "status": episode.status,
        "urgency": episode.urgency,
        "phase": episode.phase,
        "serviceLine": episode.service_line,
        "recordedControlsReady": not gate_gaps and not block_gaps and not red_conflicts and not critical_tasks,
        "who": {
            "accountableRole": episode.owner_role,
            "accountableSubject": episode.owner_subject,
            "leadName": relevant.lead_staff_name if relevant else None,
            "leadRole": relevant.lead_staff_role if relevant else None,
        },
        "what": {
            "currentPhase": episode.phase,
            "currentOrNextProcedure": relevant.procedure_name if relevant else None,
            "nextAction": episode.next_action or (tasks[0]["title"] if tasks else "Review and record the next accountable step"),
        },
        "where": {
            "areaRef": relevant.area_ref if relevant else episode.current_area_ref,
            "areaName": relevant.area_name if relevant else None,
        },
        "when": {
            "startsAt": _iso(relevant.starts_at) if relevant else None,
            "endsAt": _iso(relevant.ends_at) if relevant else None,
            "nextDeadline": next_deadline,
        },
        "how": {
            "gateGaps": gate_gaps,
            "blockers": block_gaps,
            "openTaskCount": len(tasks),
            "criticalTaskCount": len(critical_tasks),
            "openConflictCount": len(conflicts),
            "attention": attention,
        },
        "why": {
            "urgency": episode.urgency,
            "flags": flags,
            "conflicts": conflicts,
        },
        "schedule": blocks,
        "tasks": tasks,
        "links": {
            "patientCommand": "/workspace",
            "hospitalBoard": "/hospital-board",
            "episodeCommand": f"/episode-command?episode={episode.episode_ref}",
            "patientRecord": f"/patient-record?episode={episode.episode_ref}",
            "clinicalExecution": f"/clinical-execution?episode={episode.episode_ref}",
        },
        "requestedBy": {"name": auth.actor_name, "role": auth.role},
        "clinicalBoundary": "This brief summarises recorded controls and accountability. It does not replace professional clinical judgement.",
    }
