from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session, select

from app.auth import AuthContext, SENIOR_ROLES, require_authenticated
from app.database import get_session
from app.hospital_ops_models import CanonicalEpisodeState
from app.hospital_ops_service import board_snapshot, parse_json
from app.models import AuditEvent, WorkItem

router = APIRouter(prefix="/api/v14/operational-workspace", tags=["operational-workspace-v14"])


class WorkItemActionPayload(BaseModel):
    action: Literal["start", "complete", "block", "return_to_queue", "assign"]
    expectedStatus: str | None = None
    ownerRole: str | None = None
    note: str = ""


def _normalise_dt(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _iso(value: datetime | None) -> str | None:
    value = _normalise_dt(value)
    return value.isoformat() if value else None


def _work_item_dict(row: WorkItem, canonical_refs: set[str], now: datetime) -> dict[str, Any]:
    due = _normalise_dt(row.due_at)
    linked = bool(row.linked_episode_ref and row.linked_episode_ref in canonical_refs)
    return {
        "id": row.id,
        "title": row.title,
        "description": row.description,
        "category": row.category,
        "source": row.source,
        "urgency": row.urgency,
        "status": row.status,
        "ownerRole": row.owner_role,
        "ownerUserId": row.owner_user_id,
        "sectionName": row.section_name,
        "roomName": row.room_name,
        "patientName": row.linked_patient_name,
        "episodeRef": row.linked_episode_ref,
        "linkedToCanonicalEpisode": linked,
        "dueAt": _iso(row.due_at),
        "overdue": bool(due and due < now and row.status != "done"),
        "createdAt": _iso(row.created_at),
        "updatedAt": _iso(row.updated_at),
        "links": {
            "episode": f"/episode-command?episode={row.linked_episode_ref}" if linked else None,
            "patientRecord": f"/patient-record?episode={row.linked_episode_ref}" if linked else None,
        },
    }


def _gate_issue_labels(gates: dict[str, Any]) -> list[str]:
    complete_values = {True, "approved", "accepted", "authorised", "ready", "complete", "completed", "emergency_authority", "not_required"}
    labels = {
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
    issues: list[str] = []
    for key, value in gates.items():
        normal_key = str(key).strip().lower()
        if normal_key not in labels:
            continue
        if value not in complete_values:
            issues.append(labels[normal_key])
    return issues


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _block_is_current_or_future(block: dict[str, Any], now: datetime) -> bool:
    end = _normalise_dt(datetime.fromisoformat(str(block["endsAt"])))
    return bool(end and end >= now)


@router.get("")
def operational_workspace(
    premises_ref: str = "default-premises",
    operational_date: date = Query(default_factory=date.today),
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    board = board_snapshot(session, premises_ref, operational_date)
    now = datetime.now(timezone.utc)

    episodes = session.exec(
        select(CanonicalEpisodeState).where(
            CanonicalEpisodeState.premises_ref == premises_ref,
            CanonicalEpisodeState.status == "active",
        ).order_by(CanonicalEpisodeState.updated_at.desc())
    ).all()
    work_items = session.exec(
        select(WorkItem).where(WorkItem.status != "done").order_by(WorkItem.created_at.desc()).limit(150)
    ).all()

    canonical_refs = {row.episode_ref for row in episodes}
    task_rows = [_work_item_dict(row, canonical_refs, now) for row in work_items]
    tasks_by_episode: dict[str, list[dict[str, Any]]] = {}
    for task in task_rows:
        episode_ref = task.get("episodeRef")
        if episode_ref and task["linkedToCanonicalEpisode"]:
            tasks_by_episode.setdefault(str(episode_ref), []).append(task)

    block_rows = board["blocks"]
    blocks_by_episode: dict[str, list[dict[str, Any]]] = {}
    for block in block_rows:
        episode_ref = block.get("episodeRef")
        if episode_ref:
            blocks_by_episode.setdefault(str(episode_ref), []).append(block)

    conflicts_by_block: dict[str, list[dict[str, Any]]] = {}
    for conflict in board["conflicts"]:
        refs = [conflict.get("primaryBlockRef"), *(conflict.get("relatedRefs") or [])]
        for block_ref in [str(value) for value in refs if value]:
            conflicts_by_block.setdefault(block_ref, []).append(conflict)

    patient_flow: list[dict[str, Any]] = []
    for episode in episodes:
        episode_blocks = sorted(blocks_by_episode.get(episode.episode_ref, []), key=lambda item: item["startsAt"])
        episode_tasks = tasks_by_episode.get(episode.episode_ref, [])
        gates = parse_json(episode.gates_json, {}) or {}
        flags = [str(value) for value in (parse_json(episode.flags_json, []) or [])]
        episode_conflicts = [
            conflict
            for block in episode_blocks
            for conflict in conflicts_by_block.get(str(block["blockRef"]), [])
        ]
        current_block = next(
            (block for block in episode_blocks if block["status"] in {"started", "in_progress"}),
            next((block for block in episode_blocks if _block_is_current_or_future(block, now)), None),
        )
        attention = _dedupe(
            [
                *[str(conflict.get("explanation") or "") for conflict in episode_conflicts],
                *[str(task["title"]) for task in episode_tasks if task["urgency"] == "red" or task["overdue"] or task["status"] == "blocked"],
                *_gate_issue_labels(gates),
                *flags,
            ]
        )
        patient_flow.append({
            "episodeRef": episode.episode_ref,
            "patientRef": episode.patient_ref,
            "patientName": episode.patient_name,
            "serviceLine": episode.service_line,
            "urgency": episode.urgency,
            "phase": episode.phase,
            "ownerRole": episode.owner_role,
            "ownerSubject": episode.owner_subject,
            "currentAreaRef": current_block.get("areaRef") if current_block else episode.current_area_ref,
            "currentAreaName": current_block.get("areaName") if current_block else None,
            "nextAction": episode.next_action or (episode_tasks[0]["title"] if episode_tasks else "Review current care phase"),
            "scheduled": bool(episode_blocks),
            "attention": attention,
            "gates": gates,
            "flags": flags,
            "taskCount": len(episode_tasks),
            "redTaskCount": len([task for task in episode_tasks if task["urgency"] == "red"]),
            "overdueTaskCount": len([task for task in episode_tasks if task["overdue"]]),
            "schedule": [{
                "blockRef": block["blockRef"],
                "procedureName": block["procedureName"],
                "areaName": block["areaName"],
                "startsAt": block["startsAt"],
                "endsAt": block["endsAt"],
                "status": block["status"],
                "riskLevel": block["riskLevel"],
                "leadStaffName": block.get("leadStaffName"),
                "blockerCount": len(block.get("blockers") or []),
                "conflictCount": len(conflicts_by_block.get(str(block["blockRef"]), [])),
            } for block in episode_blocks[:8]],
            "links": {
                "episode": f"/episode-command?episode={episode.episode_ref}",
                "patientRecord": f"/patient-record?episode={episode.episode_ref}",
                "clinicalExecution": f"/clinical-execution?episode={episode.episode_ref}",
            },
            "version": episode.version,
        })

    unlinked_tasks = [task for task in task_rows if not task["linkedToCanonicalEpisode"]]
    linked_tasks = [task for task in task_rows if task["linkedToCanonicalEpisode"]]
    red_attention = len([task for task in task_rows if task["urgency"] == "red"]) + board["summary"]["redConflicts"]
    overdue_tasks = len([task for task in task_rows if task["overdue"]])
    scheduled_episode_refs = {str(block.get("episodeRef")) for block in block_rows if block.get("episodeRef")}

    session.commit()
    return {
        "workspaceVersion": "v14",
        "generatedAt": now.isoformat(),
        "operationalDate": operational_date.isoformat(),
        "premises": board["premises"],
        "requestedBy": {
            "subject": auth.subject,
            "name": auth.actor_name,
            "role": auth.role,
        },
        "summary": {
            "activePatients": len(patient_flow),
            "scheduledPatients": len(canonical_refs & scheduled_episode_refs),
            "unscheduledPatients": len(canonical_refs - scheduled_episode_refs),
            "boardBlocks": board["summary"]["blocks"],
            "redAttention": red_attention,
            "overdueTasks": overdue_tasks,
            "blockedTasks": len([task for task in task_rows if task["status"] == "blocked"]),
            "unlinkedTasks": len(unlinked_tasks),
        },
        "patientFlow": patient_flow,
        "tasks": linked_tasks,
        "unlinkedTasks": unlinked_tasks,
        "conflicts": board["conflicts"],
        "consistency": {
            "canonicalEpisodeCount": board["summary"]["episodes"],
            "workspacePatientCount": len(patient_flow),
            "boardBlockCount": board["summary"]["blocks"],
            "message": "The workspace and master board use the same canonical episode and operational-block records. Legacy or manually captured work remains visible separately until it is linked.",
        },
    }


@router.post("/work-items/{work_item_id}/action")
def act_on_work_item(
    work_item_id: int,
    payload: WorkItemActionPayload,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(require_authenticated),
) -> dict[str, Any]:
    item = session.get(WorkItem, work_item_id)
    if not item:
        raise HTTPException(status_code=404, detail="work item not found")
    if payload.expectedStatus is not None and item.status != payload.expectedStatus:
        raise HTTPException(status_code=409, detail={
            "message": "work item changed since it was displayed",
            "expectedStatus": payload.expectedStatus,
            "currentStatus": item.status,
        })

    owns_role = item.owner_role == auth.role
    senior = auth.role in SENIOR_ROLES
    if payload.action != "assign" and not owns_role and not senior:
        raise HTTPException(status_code=403, detail=f"work item is owned by {item.owner_role}")
    if payload.action == "assign" and not senior:
        raise HTTPException(status_code=403, detail="only a senior operational role can reassign work")

    allowed_from = {
        "start": {"new"},
        "complete": {"new", "in_progress", "blocked"},
        "block": {"new", "in_progress"},
        "return_to_queue": {"in_progress", "blocked"},
        "assign": {"new", "in_progress", "blocked"},
    }
    if item.status not in allowed_from[payload.action]:
        raise HTTPException(status_code=409, detail=f"cannot {payload.action} a work item in {item.status} state")

    before_status = item.status
    if payload.action == "start":
        item.status = "in_progress"
    elif payload.action == "complete":
        item.status = "done"
    elif payload.action == "block":
        item.status = "blocked"
    elif payload.action == "return_to_queue":
        item.status = "new"
        item.owner_user_id = None
    elif payload.action == "assign":
        if not payload.ownerRole:
            raise HTTPException(status_code=422, detail="ownerRole is required for assignment")
        item.owner_role = payload.ownerRole
        item.owner_user_id = None

    item.updated_at = datetime.now(timezone.utc)
    session.add(item)
    session.flush()
    audit = AuditEvent(
        actor_name=auth.actor_name,
        action=f"workspace_{payload.action}",
        entity_type="work_item",
        entity_id=item.id or 0,
        summary=payload.note.strip() or f"{payload.action} {item.title}; {before_status} -> {item.status}; owner {item.owner_role}",
    )
    session.add(audit)
    session.commit()
    session.refresh(item)
    session.refresh(audit)
    return {
        "ok": True,
        "workItem": _work_item_dict(item, {item.linked_episode_ref} if item.linked_episode_ref else set(), datetime.now(timezone.utc)),
        "audit": {
            "id": audit.id,
            "actorName": audit.actor_name,
            "action": audit.action,
            "createdAt": _iso(audit.created_at),
        },
    }
